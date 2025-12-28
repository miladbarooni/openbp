/**
 * @file node.hpp
 * @brief BPNode class for branch-and-price tree nodes.
 *
 * A BPNode represents a node in the B&P search tree, storing bounds,
 * branching decisions, solution information, and node status.
 */

#pragma once

#include <vector>
#include <memory>
#include <limits>
#include <cstdint>
#include <string>
#include <optional>
#include <variant>

namespace openbp {

/**
 * @brief Status of a B&P tree node.
 */
enum class NodeStatus : uint8_t {
    PENDING,      // Not yet processed
    PROCESSING,   // Currently being processed
    BRANCHED,     // Branched into children
    PRUNED_BOUND, // Pruned by bound
    PRUNED_INFEASIBLE,  // LP relaxation infeasible
    INTEGER,      // Integer solution found
    FATHOMED      // Fathomed (other reason)
};

/**
 * @brief Type of branching decision.
 */
enum class BranchType : uint8_t {
    VARIABLE,       // Standard variable branching (x_j <= k or x_j >= k+1)
    RYAN_FOSTER,    // Ryan-Foster: pair (i,j) same/different column
    ARC,            // Arc branching: arc in/out of solution
    RESOURCE,       // Resource window branching
    CUSTOM          // User-defined branching
};

/**
 * @brief A single branching decision.
 *
 * Branching decisions are polymorphic - the interpretation depends on
 * the branch type. This allows different branching strategies to store
 * their decisions in a uniform container.
 */
struct BranchingDecision {
    BranchType type;

    // For VARIABLE branching
    int32_t variable_index = -1;
    double bound_value = 0.0;
    bool is_upper_bound = false;  // true = x <= k, false = x >= k

    // For RYAN_FOSTER branching
    int32_t item_i = -1;
    int32_t item_j = -1;
    bool same_column = false;  // true = must be together, false = must be apart

    // For ARC branching
    int32_t arc_index = -1;
    int32_t source_node = -1;
    bool arc_required = false;  // true = arc must be used, false = forbidden

    // For RESOURCE branching
    int32_t resource_index = -1;
    double lower_bound = 0.0;
    double upper_bound = std::numeric_limits<double>::infinity();

    // For CUSTOM branching - opaque data that strategies can interpret
    std::vector<int32_t> custom_int_data;
    std::vector<double> custom_float_data;

    // Factory methods
    static BranchingDecision variable_branch(int32_t var_idx, double value, bool upper) {
        BranchingDecision d;
        d.type = BranchType::VARIABLE;
        d.variable_index = var_idx;
        d.bound_value = value;
        d.is_upper_bound = upper;
        return d;
    }

    static BranchingDecision ryan_foster(int32_t i, int32_t j, bool same) {
        BranchingDecision d;
        d.type = BranchType::RYAN_FOSTER;
        d.item_i = i;
        d.item_j = j;
        d.same_column = same;
        return d;
    }

    static BranchingDecision arc_branch(int32_t arc, int32_t source, bool required) {
        BranchingDecision d;
        d.type = BranchType::ARC;
        d.arc_index = arc;
        d.source_node = source;
        d.arc_required = required;
        return d;
    }

    static BranchingDecision resource_branch(int32_t res_idx, double lb, double ub) {
        BranchingDecision d;
        d.type = BranchType::RESOURCE;
        d.resource_index = res_idx;
        d.lower_bound = lb;
        d.upper_bound = ub;
        return d;
    }
};

/**
 * @brief A node in the branch-and-price tree.
 *
 * BPNode is a lightweight, cache-efficient structure optimized for
 * tree traversal and node management. It stores:
 * - Bounds (lower/upper from LP relaxation)
 * - Branching decisions accumulated from root
 * - Solution information
 * - Tree structure (parent/children)
 */
class BPNode {
public:
    using NodeId = int64_t;
    static constexpr NodeId INVALID_ID = -1;
    static constexpr double INF = std::numeric_limits<double>::infinity();

    /**
     * @brief Construct the root node.
     */
    BPNode()
        : id_(0)
        , parent_id_(INVALID_ID)
        , depth_(0)
        , lower_bound_(-INF)
        , upper_bound_(INF)
        , lp_value_(INF)
        , status_(NodeStatus::PENDING)
        , is_integer_(false)
    {}

    /**
     * @brief Construct a child node.
     * @param id Unique node identifier
     * @param parent_id Parent node ID
     * @param depth Depth in tree (parent depth + 1)
     * @param decision The branching decision leading to this node
     */
    BPNode(NodeId id, NodeId parent_id, int32_t depth, const BranchingDecision& decision)
        : id_(id)
        , parent_id_(parent_id)
        , depth_(depth)
        , lower_bound_(-INF)
        , upper_bound_(INF)
        , lp_value_(INF)
        , status_(NodeStatus::PENDING)
        , is_integer_(false)
    {
        local_decisions_.push_back(decision);
    }

    // Accessors
    NodeId id() const { return id_; }
    NodeId parent_id() const { return parent_id_; }
    int32_t depth() const { return depth_; }

    double lower_bound() const { return lower_bound_; }
    double upper_bound() const { return upper_bound_; }
    double lp_value() const { return lp_value_; }
    double gap() const {
        if (upper_bound_ == INF || lower_bound_ == -INF) return INF;
        if (upper_bound_ == 0.0) return (lower_bound_ == 0.0) ? 0.0 : INF;
        return (upper_bound_ - lower_bound_) / std::abs(upper_bound_);
    }

    NodeStatus status() const { return status_; }
    bool is_integer() const { return is_integer_; }
    bool is_processed() const {
        return status_ != NodeStatus::PENDING && status_ != NodeStatus::PROCESSING;
    }
    bool is_pruned() const {
        return status_ == NodeStatus::PRUNED_BOUND ||
               status_ == NodeStatus::PRUNED_INFEASIBLE ||
               status_ == NodeStatus::FATHOMED;
    }
    bool can_be_explored() const {
        return status_ == NodeStatus::PENDING;
    }

    // Branching decisions
    const std::vector<BranchingDecision>& local_decisions() const { return local_decisions_; }
    const std::vector<BranchingDecision>& inherited_decisions() const { return inherited_decisions_; }

    /**
     * @brief Get all branching decisions (inherited + local).
     */
    std::vector<BranchingDecision> all_decisions() const {
        std::vector<BranchingDecision> all = inherited_decisions_;
        all.insert(all.end(), local_decisions_.begin(), local_decisions_.end());
        return all;
    }

    size_t num_decisions() const {
        return inherited_decisions_.size() + local_decisions_.size();
    }

    // Children
    const std::vector<NodeId>& children() const { return children_; }
    bool has_children() const { return !children_.empty(); }

    // Modifiers
    void set_id(NodeId id) { id_ = id; }
    void set_lower_bound(double lb) { lower_bound_ = lb; }
    void set_upper_bound(double ub) { upper_bound_ = ub; }
    void set_lp_value(double val) { lp_value_ = val; }
    void set_status(NodeStatus status) { status_ = status; }
    void set_is_integer(bool is_int) { is_integer_ = is_int; }

    void add_local_decision(const BranchingDecision& decision) {
        local_decisions_.push_back(decision);
    }

    void set_inherited_decisions(std::vector<BranchingDecision>&& decisions) {
        inherited_decisions_ = std::move(decisions);
    }

    void add_child(NodeId child_id) {
        children_.push_back(child_id);
    }

    /**
     * @brief Mark node as pruned by bound.
     * @param global_upper Current global upper bound
     * @return true if pruned, false otherwise
     */
    bool try_prune_by_bound(double global_upper) {
        if (lower_bound_ >= global_upper - 1e-6) {
            status_ = NodeStatus::PRUNED_BOUND;
            return true;
        }
        return false;
    }

    // Solution storage (optional - only for integer nodes)
    void set_solution(std::vector<double>&& sol) { solution_ = std::move(sol); }
    const std::vector<double>& solution() const { return solution_; }
    bool has_solution() const { return !solution_.empty(); }

    // Column indices in the solution (for sparse representation)
    void set_solution_columns(std::vector<int32_t>&& cols) { solution_columns_ = std::move(cols); }
    const std::vector<int32_t>& solution_columns() const { return solution_columns_; }

private:
    NodeId id_;
    NodeId parent_id_;
    int32_t depth_;

    double lower_bound_;
    double upper_bound_;
    double lp_value_;

    NodeStatus status_;
    bool is_integer_;

    // Branching decisions leading to this node
    std::vector<BranchingDecision> inherited_decisions_;  // From ancestors
    std::vector<BranchingDecision> local_decisions_;      // At this node

    // Tree structure
    std::vector<NodeId> children_;

    // Solution (sparse)
    std::vector<double> solution_;
    std::vector<int32_t> solution_columns_;
};

/**
 * @brief Convert NodeStatus to string.
 */
inline const char* node_status_to_string(NodeStatus status) {
    switch (status) {
        case NodeStatus::PENDING: return "PENDING";
        case NodeStatus::PROCESSING: return "PROCESSING";
        case NodeStatus::BRANCHED: return "BRANCHED";
        case NodeStatus::PRUNED_BOUND: return "PRUNED_BOUND";
        case NodeStatus::PRUNED_INFEASIBLE: return "PRUNED_INFEASIBLE";
        case NodeStatus::INTEGER: return "INTEGER";
        case NodeStatus::FATHOMED: return "FATHOMED";
        default: return "UNKNOWN";
    }
}

/**
 * @brief Convert BranchType to string.
 */
inline const char* branch_type_to_string(BranchType type) {
    switch (type) {
        case BranchType::VARIABLE: return "VARIABLE";
        case BranchType::RYAN_FOSTER: return "RYAN_FOSTER";
        case BranchType::ARC: return "ARC";
        case BranchType::RESOURCE: return "RESOURCE";
        case BranchType::CUSTOM: return "CUSTOM";
        default: return "UNKNOWN";
    }
}

}  // namespace openbp
