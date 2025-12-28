/**
 * @file selection.hpp
 * @brief Node selection policies for branch-and-price.
 *
 * Provides efficient C++ implementations of node selection strategies
 * that determine the order of node exploration in the B&P tree.
 */

#pragma once

#include "node.hpp"
#include "tree.hpp"

#include <queue>
#include <functional>
#include <algorithm>
#include <cmath>
#include <random>

namespace openbp {

/**
 * @brief Abstract base class for node selection policies.
 *
 * Subclasses implement different strategies for selecting the next
 * node to explore in the B&P tree.
 */
class NodeSelector {
public:
    virtual ~NodeSelector() = default;

    /**
     * @brief Add a node to the open queue.
     * @param node Pointer to the node
     */
    virtual void add_node(BPNode* node) = 0;

    /**
     * @brief Add multiple nodes to the open queue.
     * @param nodes Vector of node pointers
     */
    virtual void add_nodes(const std::vector<BPNode*>& nodes) {
        for (auto* node : nodes) {
            add_node(node);
        }
    }

    /**
     * @brief Select and remove the next node to explore.
     * @return Pointer to the selected node, or nullptr if empty
     */
    virtual BPNode* select_next() = 0;

    /**
     * @brief Peek at the next node without removing it.
     * @return Pointer to the next node, or nullptr if empty
     */
    virtual BPNode* peek_next() const = 0;

    /**
     * @brief Check if there are any open nodes.
     */
    virtual bool empty() const = 0;

    /**
     * @brief Get the number of open nodes.
     */
    virtual size_t size() const = 0;

    /**
     * @brief Remove pruned nodes from the queue.
     * @return Number of nodes removed
     */
    virtual size_t prune() = 0;

    /**
     * @brief Update after global bound improvement.
     * Called when the global upper bound is updated.
     * @param new_bound The new global upper bound
     */
    virtual void on_bound_update(double new_bound) {
        // Default: do nothing. Subclasses can override.
    }

    /**
     * @brief Get the best (lowest) bound among open nodes.
     */
    virtual double best_bound() const = 0;

    /**
     * @brief Get all open node IDs (for debugging/reporting).
     */
    virtual std::vector<BPNode::NodeId> get_open_node_ids() const = 0;

    /**
     * @brief Clear all nodes from the selector.
     */
    virtual void clear() = 0;
};


/**
 * @brief Best-first (best-bound) node selection.
 *
 * Always explores the node with the lowest lower bound.
 * This minimizes the number of nodes explored but may delay
 * finding good integer solutions.
 */
class BestFirstSelector : public NodeSelector {
public:
    BestFirstSelector() = default;

    void add_node(BPNode* node) override {
        if (node && node->can_be_explored()) {
            queue_.push(node);
        }
    }

    BPNode* select_next() override {
        prune();
        if (queue_.empty()) return nullptr;

        BPNode* node = queue_.top();
        queue_.pop();
        return node;
    }

    BPNode* peek_next() const override {
        if (queue_.empty()) return nullptr;
        return queue_.top();
    }

    bool empty() const override {
        return queue_.empty();
    }

    size_t size() const override {
        return queue_.size();
    }

    size_t prune() override {
        // Remove nodes that are no longer explorable
        std::vector<BPNode*> valid;
        size_t removed = 0;

        while (!queue_.empty()) {
            BPNode* node = queue_.top();
            queue_.pop();
            if (node->can_be_explored()) {
                valid.push_back(node);
            } else {
                removed++;
            }
        }

        for (auto* node : valid) {
            queue_.push(node);
        }

        return removed;
    }

    double best_bound() const override {
        if (queue_.empty()) return std::numeric_limits<double>::infinity();
        return queue_.top()->lower_bound();
    }

    std::vector<BPNode::NodeId> get_open_node_ids() const override {
        std::vector<BPNode::NodeId> ids;
        auto copy = queue_;
        while (!copy.empty()) {
            ids.push_back(copy.top()->id());
            copy.pop();
        }
        return ids;
    }

    void clear() override {
        while (!queue_.empty()) queue_.pop();
    }

private:
    struct CompareByBound {
        bool operator()(const BPNode* a, const BPNode* b) const {
            // Min-heap: lower bound is better
            return a->lower_bound() > b->lower_bound();
        }
    };

    std::priority_queue<BPNode*, std::vector<BPNode*>, CompareByBound> queue_;
};


/**
 * @brief Depth-first node selection (diving).
 *
 * Explores deepest nodes first, which tends to find integer
 * solutions quickly. Uses best-bound as tiebreaker.
 */
class DepthFirstSelector : public NodeSelector {
public:
    DepthFirstSelector() = default;

    void add_node(BPNode* node) override {
        if (node && node->can_be_explored()) {
            queue_.push(node);
        }
    }

    BPNode* select_next() override {
        prune();
        if (queue_.empty()) return nullptr;

        BPNode* node = queue_.top();
        queue_.pop();
        return node;
    }

    BPNode* peek_next() const override {
        if (queue_.empty()) return nullptr;
        return queue_.top();
    }

    bool empty() const override {
        return queue_.empty();
    }

    size_t size() const override {
        return queue_.size();
    }

    size_t prune() override {
        std::vector<BPNode*> valid;
        size_t removed = 0;

        while (!queue_.empty()) {
            BPNode* node = queue_.top();
            queue_.pop();
            if (node->can_be_explored()) {
                valid.push_back(node);
            } else {
                removed++;
            }
        }

        for (auto* node : valid) {
            queue_.push(node);
        }

        return removed;
    }

    double best_bound() const override {
        if (queue_.empty()) return std::numeric_limits<double>::infinity();

        double best = std::numeric_limits<double>::infinity();
        auto copy = queue_;
        while (!copy.empty()) {
            best = std::min(best, copy.top()->lower_bound());
            copy.pop();
        }
        return best;
    }

    std::vector<BPNode::NodeId> get_open_node_ids() const override {
        std::vector<BPNode::NodeId> ids;
        auto copy = queue_;
        while (!copy.empty()) {
            ids.push_back(copy.top()->id());
            copy.pop();
        }
        return ids;
    }

    void clear() override {
        while (!queue_.empty()) queue_.pop();
    }

private:
    struct CompareByDepth {
        bool operator()(const BPNode* a, const BPNode* b) const {
            // Max-heap for depth: deeper is better
            if (a->depth() != b->depth()) {
                return a->depth() < b->depth();
            }
            // Tiebreaker: lower bound
            return a->lower_bound() > b->lower_bound();
        }
    };

    std::priority_queue<BPNode*, std::vector<BPNode*>, CompareByDepth> queue_;
};


/**
 * @brief Best-estimate node selection.
 *
 * Uses a combination of lower bound and an estimate of the
 * integer objective to prioritize nodes likely to lead to
 * good solutions.
 *
 * Estimate = lower_bound + estimate_weight * (depth / max_depth) * gap
 */
class BestEstimateSelector : public NodeSelector {
public:
    /**
     * @brief Construct a best-estimate selector.
     * @param estimate_weight Weight for the depth-based estimate (default 0.5)
     */
    explicit BestEstimateSelector(double estimate_weight = 0.5)
        : estimate_weight_(estimate_weight)
        , global_upper_bound_(std::numeric_limits<double>::infinity())
        , max_depth_(1)
    {}

    void add_node(BPNode* node) override {
        if (node && node->can_be_explored()) {
            nodes_.push_back(node);
            max_depth_ = std::max(max_depth_, static_cast<int64_t>(node->depth()));
        }
    }

    BPNode* select_next() override {
        prune();
        if (nodes_.empty()) return nullptr;

        // Find node with best estimate
        auto best_it = std::min_element(nodes_.begin(), nodes_.end(),
            [this](const BPNode* a, const BPNode* b) {
                return estimate(a) < estimate(b);
            });

        BPNode* node = *best_it;
        nodes_.erase(best_it);
        return node;
    }

    BPNode* peek_next() const override {
        if (nodes_.empty()) return nullptr;

        auto best_it = std::min_element(nodes_.begin(), nodes_.end(),
            [this](const BPNode* a, const BPNode* b) {
                return estimate(a) < estimate(b);
            });

        return *best_it;
    }

    bool empty() const override {
        return nodes_.empty();
    }

    size_t size() const override {
        return nodes_.size();
    }

    size_t prune() override {
        size_t old_size = nodes_.size();
        nodes_.erase(
            std::remove_if(nodes_.begin(), nodes_.end(),
                [](BPNode* n) { return !n->can_be_explored(); }),
            nodes_.end()
        );
        return old_size - nodes_.size();
    }

    void on_bound_update(double new_bound) override {
        global_upper_bound_ = new_bound;
    }

    double best_bound() const override {
        if (nodes_.empty()) return std::numeric_limits<double>::infinity();

        double best = std::numeric_limits<double>::infinity();
        for (const auto* node : nodes_) {
            best = std::min(best, node->lower_bound());
        }
        return best;
    }

    std::vector<BPNode::NodeId> get_open_node_ids() const override {
        std::vector<BPNode::NodeId> ids;
        ids.reserve(nodes_.size());
        for (const auto* node : nodes_) {
            ids.push_back(node->id());
        }
        return ids;
    }

    void clear() override {
        nodes_.clear();
    }

private:
    double estimate(const BPNode* node) const {
        double lb = node->lower_bound();

        if (global_upper_bound_ == std::numeric_limits<double>::infinity()) {
            // No incumbent yet - use depth penalty to encourage diving
            return lb - estimate_weight_ * node->depth();
        }

        // Estimate based on depth progress toward integer
        double depth_ratio = static_cast<double>(node->depth()) / static_cast<double>(std::max(static_cast<int64_t>(1), max_depth_));
        double gap = global_upper_bound_ - lb;
        return lb + estimate_weight_ * (1.0 - depth_ratio) * gap;
    }

    std::vector<BPNode*> nodes_;
    double estimate_weight_;
    double global_upper_bound_;
    int64_t max_depth_;
};


/**
 * @brief Hybrid node selection with periodic diving.
 *
 * Alternates between best-first and depth-first selection
 * to balance bound improvement and solution finding.
 */
class HybridSelector : public NodeSelector {
public:
    /**
     * @brief Construct a hybrid selector.
     * @param dive_frequency How often to dive (1 = every node, higher = less often)
     * @param dive_depth How deep to dive before switching back
     */
    HybridSelector(int dive_frequency = 5, int dive_depth = 10)
        : dive_frequency_(dive_frequency)
        , dive_depth_(dive_depth)
        , nodes_since_dive_(0)
        , current_dive_depth_(0)
        , diving_(false)
    {}

    void add_node(BPNode* node) override {
        if (node && node->can_be_explored()) {
            best_first_.add_node(node);
            depth_first_.add_node(node);
        }
    }

    void add_nodes(const std::vector<BPNode*>& nodes) override {
        for (auto* node : nodes) {
            if (node && node->can_be_explored()) {
                best_first_.add_node(node);
                depth_first_.add_node(node);
            }
        }
    }

    BPNode* select_next() override {
        // Decide whether to dive
        if (!diving_ && nodes_since_dive_ >= dive_frequency_) {
            diving_ = true;
            current_dive_depth_ = 0;
        }

        if (diving_) {
            BPNode* node = depth_first_.select_next();
            if (node) {
                current_dive_depth_++;
                if (current_dive_depth_ >= dive_depth_) {
                    diving_ = false;
                    nodes_since_dive_ = 0;
                }
                // Remove from best_first too (it's a duplicate)
                best_first_.prune();
                return node;
            }
            // Depth-first is empty, switch to best-first
            diving_ = false;
        }

        nodes_since_dive_++;
        depth_first_.prune();
        return best_first_.select_next();
    }

    BPNode* peek_next() const override {
        if (diving_) {
            return depth_first_.peek_next();
        }
        return best_first_.peek_next();
    }

    bool empty() const override {
        return best_first_.empty();
    }

    size_t size() const override {
        return best_first_.size();
    }

    size_t prune() override {
        size_t removed1 = best_first_.prune();
        size_t removed2 = depth_first_.prune();
        return std::max(removed1, removed2);
    }

    double best_bound() const override {
        return best_first_.best_bound();
    }

    std::vector<BPNode::NodeId> get_open_node_ids() const override {
        return best_first_.get_open_node_ids();
    }

    void clear() override {
        best_first_.clear();
        depth_first_.clear();
        nodes_since_dive_ = 0;
        current_dive_depth_ = 0;
        diving_ = false;
    }

private:
    BestFirstSelector best_first_;
    DepthFirstSelector depth_first_;
    int dive_frequency_;
    int dive_depth_;
    int nodes_since_dive_;
    int current_dive_depth_;
    bool diving_;
};


/**
 * @brief Factory function to create node selectors by name.
 * @param name Selector name: "best_first", "depth_first", "best_estimate", "hybrid"
 * @return Unique pointer to the selector
 */
inline std::unique_ptr<NodeSelector> create_selector(const std::string& name) {
    if (name == "best_first" || name == "BestFirst") {
        return std::make_unique<BestFirstSelector>();
    } else if (name == "depth_first" || name == "DepthFirst") {
        return std::make_unique<DepthFirstSelector>();
    } else if (name == "best_estimate" || name == "BestEstimate") {
        return std::make_unique<BestEstimateSelector>();
    } else if (name == "hybrid" || name == "Hybrid") {
        return std::make_unique<HybridSelector>();
    }
    // Default to best-first
    return std::make_unique<BestFirstSelector>();
}

}  // namespace openbp
