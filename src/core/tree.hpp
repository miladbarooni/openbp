/**
 * @file tree.hpp
 * @brief BPTree class for managing the branch-and-price search tree.
 *
 * The BPTree provides efficient storage, node management, and
 * traversal for the B&P algorithm.
 */

#pragma once

#include "node.hpp"
#include "node_pool.hpp"

#include <queue>
#include <functional>
#include <unordered_map>
#include <memory>
#include <atomic>
#include <mutex>

namespace openbp {

/**
 * @brief Statistics about the B&P tree.
 */
struct TreeStats {
    int64_t nodes_created = 0;
    int64_t nodes_processed = 0;
    int64_t nodes_pruned_bound = 0;
    int64_t nodes_pruned_infeasible = 0;
    int64_t nodes_integer = 0;
    int64_t nodes_branched = 0;
    int64_t nodes_open = 0;
    int64_t max_depth = 0;
    double best_lower_bound = -std::numeric_limits<double>::infinity();
    double best_upper_bound = std::numeric_limits<double>::infinity();

    double gap() const {
        if (best_upper_bound == std::numeric_limits<double>::infinity() ||
            best_lower_bound == -std::numeric_limits<double>::infinity()) {
            return std::numeric_limits<double>::infinity();
        }
        if (std::abs(best_upper_bound) < 1e-10) {
            return (std::abs(best_lower_bound) < 1e-10) ? 0.0 : std::numeric_limits<double>::infinity();
        }
        return (best_upper_bound - best_lower_bound) / std::abs(best_upper_bound);
    }
};

/**
 * @brief The branch-and-price search tree.
 *
 * Manages node storage, open node queue, and tree statistics.
 * Designed for efficiency and thread-safety (for future parallel B&P).
 */
class BPTree {
public:
    using NodeId = BPNode::NodeId;
    using NodePtr = BPNode*;
    using ConstNodePtr = const BPNode*;

    /**
     * @brief Construct an empty tree.
     * @param minimize true for minimization, false for maximization
     */
    explicit BPTree(bool minimize = true)
        : minimize_(minimize)
        , next_id_(0)
        , global_lower_bound_(-std::numeric_limits<double>::infinity())
        , global_upper_bound_(std::numeric_limits<double>::infinity())
    {
        // Create root node
        root_ = node_pool_.allocate();
        root_->set_id(next_id_++);
        nodes_[root_->id()] = root_;
        stats_.nodes_created = 1;
        stats_.nodes_open = 1;
    }

    // Non-copyable
    BPTree(const BPTree&) = delete;
    BPTree& operator=(const BPTree&) = delete;

    // Movable
    BPTree(BPTree&&) = default;
    BPTree& operator=(BPTree&&) = default;

    // Root access
    NodePtr root() { return root_; }
    ConstNodePtr root() const { return root_; }
    NodeId root_id() const { return root_ ? root_->id() : BPNode::INVALID_ID; }

    // Node access
    NodePtr node(NodeId id) {
        auto it = nodes_.find(id);
        return (it != nodes_.end()) ? it->second : nullptr;
    }

    ConstNodePtr node(NodeId id) const {
        auto it = nodes_.find(id);
        return (it != nodes_.end()) ? it->second : nullptr;
    }

    bool has_node(NodeId id) const {
        return nodes_.find(id) != nodes_.end();
    }

    size_t num_nodes() const { return nodes_.size(); }

    /**
     * @brief Create a child node from a branching decision.
     * @param parent Parent node
     * @param decision The branching decision
     * @return Pointer to the new child node
     */
    NodePtr create_child(NodePtr parent, const BranchingDecision& decision) {
        NodePtr child = node_pool_.allocate();
        NodeId child_id = next_id_++;

        // Initialize child
        *child = BPNode(child_id, parent->id(), parent->depth() + 1, decision);

        // Inherit parent's decisions
        auto inherited = parent->all_decisions();
        child->set_inherited_decisions(std::move(inherited));

        // Initialize bounds from parent
        child->set_lower_bound(parent->lower_bound());
        child->set_upper_bound(parent->upper_bound());

        // Link to parent
        parent->add_child(child_id);

        // Add to tree
        nodes_[child_id] = child;

        // Update stats
        stats_.nodes_created++;
        stats_.nodes_open++;
        if (child->depth() > stats_.max_depth) {
            stats_.max_depth = child->depth();
        }

        return child;
    }

    /**
     * @brief Create multiple children from branching (common case: binary branching).
     * @param parent Parent node
     * @param decisions Vector of branching decisions (one per child)
     * @return Vector of pointers to new child nodes
     */
    std::vector<NodePtr> create_children(NodePtr parent, const std::vector<BranchingDecision>& decisions) {
        std::vector<NodePtr> children;
        children.reserve(decisions.size());

        for (const auto& decision : decisions) {
            children.push_back(create_child(parent, decision));
        }

        // Mark parent as branched
        parent->set_status(NodeStatus::BRANCHED);
        stats_.nodes_branched++;
        stats_.nodes_open--;  // Parent is no longer open

        return children;
    }

    /**
     * @brief Mark a node as processed and update statistics.
     */
    void mark_processed(NodePtr node, NodeStatus new_status) {
        NodeStatus old_status = node->status();
        node->set_status(new_status);

        if (old_status == NodeStatus::PENDING || old_status == NodeStatus::PROCESSING) {
            stats_.nodes_processed++;
            if (new_status != NodeStatus::BRANCHED) {
                stats_.nodes_open--;
            }
        }

        switch (new_status) {
            case NodeStatus::PRUNED_BOUND:
                stats_.nodes_pruned_bound++;
                break;
            case NodeStatus::PRUNED_INFEASIBLE:
                stats_.nodes_pruned_infeasible++;
                break;
            case NodeStatus::INTEGER:
                stats_.nodes_integer++;
                break;
            default:
                break;
        }
    }

    // Bounds management
    double global_lower_bound() const { return global_lower_bound_; }
    double global_upper_bound() const { return global_upper_bound_; }

    void set_global_lower_bound(double lb) { global_lower_bound_ = lb; }
    void set_global_upper_bound(double ub) { global_upper_bound_ = ub; }

    bool is_minimizing() const { return minimize_; }

    /**
     * @brief Update bounds after processing a node.
     * @param node The node that was processed
     * @return true if global upper bound was improved
     */
    bool update_bounds(NodePtr node) {
        bool improved = false;

        // If integer solution found, update upper bound
        if (node->is_integer() && node->lp_value() < global_upper_bound_) {
            global_upper_bound_ = node->lp_value();
            stats_.best_upper_bound = global_upper_bound_;
            improved = true;
        }

        // Update lower bound from best open node
        // (This is called by the solver after updating the open node queue)

        return improved;
    }

    /**
     * @brief Compute the global lower bound from open nodes.
     * @param open_node_ids IDs of currently open nodes
     * @return The minimum lower bound among open nodes
     */
    double compute_lower_bound(const std::vector<NodeId>& open_node_ids) const {
        double lb = global_upper_bound_;
        for (NodeId id : open_node_ids) {
            auto it = nodes_.find(id);
            if (it != nodes_.end() && it->second->can_be_explored()) {
                lb = std::min(lb, it->second->lower_bound());
            }
        }
        return lb;
    }

    /**
     * @brief Try to prune nodes by bound.
     * @return Number of nodes pruned
     */
    int64_t prune_by_bound() {
        int64_t pruned = 0;
        for (auto& [id, node] : nodes_) {
            if (node->can_be_explored() && node->try_prune_by_bound(global_upper_bound_)) {
                stats_.nodes_pruned_bound++;
                stats_.nodes_open--;
                pruned++;
            }
        }
        return pruned;
    }

    /**
     * @brief Get all open node IDs.
     */
    std::vector<NodeId> get_open_nodes() const {
        std::vector<NodeId> open;
        for (const auto& [id, node] : nodes_) {
            if (node->can_be_explored()) {
                open.push_back(id);
            }
        }
        return open;
    }

    /**
     * @brief Check if tree exploration is complete.
     */
    bool is_complete() const {
        return stats_.nodes_open == 0;
    }

    /**
     * @brief Get current gap.
     */
    double gap() const {
        if (global_upper_bound_ == std::numeric_limits<double>::infinity() ||
            global_lower_bound_ == -std::numeric_limits<double>::infinity()) {
            return std::numeric_limits<double>::infinity();
        }
        if (std::abs(global_upper_bound_) < 1e-10) {
            return (std::abs(global_lower_bound_) < 1e-10) ? 0.0 : std::numeric_limits<double>::infinity();
        }
        return (global_upper_bound_ - global_lower_bound_) / std::abs(global_upper_bound_);
    }

    // Statistics
    const TreeStats& stats() const { return stats_; }
    TreeStats& stats() { return stats_; }

    /**
     * @brief Iterate over all nodes.
     * @param callback Function to call for each node
     */
    template<typename Func>
    void for_each_node(Func&& callback) {
        for (auto& [id, node] : nodes_) {
            callback(node);
        }
    }

    template<typename Func>
    void for_each_node(Func&& callback) const {
        for (const auto& [id, node] : nodes_) {
            callback(node);
        }
    }

    /**
     * @brief Get the path from root to a node.
     * @param target_id ID of the target node
     * @return Vector of node IDs from root to target
     */
    std::vector<NodeId> get_path_to_root(NodeId target_id) const {
        std::vector<NodeId> path;
        NodeId current = target_id;

        while (current != BPNode::INVALID_ID) {
            path.push_back(current);
            auto it = nodes_.find(current);
            if (it == nodes_.end()) break;
            current = it->second->parent_id();
        }

        std::reverse(path.begin(), path.end());
        return path;
    }

    /**
     * @brief Get the incumbent (best integer solution) node.
     * @return Pointer to the incumbent node, or nullptr if none
     */
    ConstNodePtr incumbent() const { return incumbent_; }
    NodePtr incumbent() { return incumbent_; }

    void set_incumbent(NodePtr node) {
        incumbent_ = node;
        if (node) {
            global_upper_bound_ = node->lp_value();
            stats_.best_upper_bound = global_upper_bound_;
        }
    }

private:
    bool minimize_;
    NodePool<BPNode> node_pool_;
    std::unordered_map<NodeId, NodePtr> nodes_;
    NodePtr root_ = nullptr;
    NodePtr incumbent_ = nullptr;
    int64_t next_id_;

    double global_lower_bound_;
    double global_upper_bound_;

    TreeStats stats_;
};

}  // namespace openbp
