/**
 * @file node_pool.hpp
 * @brief Memory pool for efficient node allocation.
 *
 * Provides cache-efficient node allocation and deallocation
 * to minimize memory fragmentation and improve performance.
 */

#pragma once

#include <vector>
#include <memory>
#include <cstdint>

namespace openbp {

/**
 * @brief Simple object pool for node allocation.
 *
 * Allocates nodes in chunks to reduce allocation overhead
 * and improve cache locality. Nodes are never individually
 * freed during tree construction - the entire pool is
 * released when the tree is destroyed.
 *
 * @tparam T The node type to pool
 */
template<typename T>
class NodePool {
public:
    static constexpr size_t DEFAULT_CHUNK_SIZE = 1024;

    explicit NodePool(size_t chunk_size = DEFAULT_CHUNK_SIZE)
        : chunk_size_(chunk_size)
        , next_in_chunk_(0)
        , total_allocated_(0)
    {
        allocate_chunk();
    }

    // Non-copyable
    NodePool(const NodePool&) = delete;
    NodePool& operator=(const NodePool&) = delete;

    // Movable
    NodePool(NodePool&&) = default;
    NodePool& operator=(NodePool&&) = default;

    /**
     * @brief Allocate a new node.
     * @return Pointer to the allocated node
     */
    T* allocate() {
        if (next_in_chunk_ >= chunk_size_) {
            allocate_chunk();
        }

        T* node = &chunks_.back()[next_in_chunk_++];
        total_allocated_++;
        return node;
    }

    /**
     * @brief Get the total number of allocated nodes.
     */
    size_t size() const { return total_allocated_; }

    /**
     * @brief Get the number of chunks allocated.
     */
    size_t num_chunks() const { return chunks_.size(); }

    /**
     * @brief Get the total memory used (approximate).
     */
    size_t memory_usage() const {
        return chunks_.size() * chunk_size_ * sizeof(T);
    }

    /**
     * @brief Clear all allocated nodes.
     *
     * This doesn't free memory but resets the pool for reuse.
     */
    void clear() {
        chunks_.clear();
        next_in_chunk_ = 0;
        total_allocated_ = 0;
        allocate_chunk();
    }

private:
    void allocate_chunk() {
        chunks_.emplace_back(std::make_unique<T[]>(chunk_size_));
        next_in_chunk_ = 0;
    }

    size_t chunk_size_;
    size_t next_in_chunk_;
    size_t total_allocated_;
    std::vector<std::unique_ptr<T[]>> chunks_;
};

}  // namespace openbp
