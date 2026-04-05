package com.example.voting.repository;

import com.example.voting.model.Origami;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * Enhanced repository interface for Origami entities.
 * 
 * Provides comprehensive data access methods with proper transaction management,
 * atomic operations, and performance optimizations.
 */
@Repository
public interface OrigamiRepository extends JpaRepository<Origami, Long> {

    /**
     * Find all active origami items.
     */
    List<Origami> findByActiveTrue();

    /**
     * Find all active origami items with pagination.
     */
    Page<Origami> findByActiveTrue(Pageable pageable);

    /**
     * Find an origami by external ID and active status.
     */
    Optional<Origami> findByOrigamiIdAndActiveTrue(String origamiId);

    /**
     * Find an origami by external ID regardless of active status.
     */
    Optional<Origami> findByOrigamiId(String origamiId);

    /**
     * Count origami items by external ID.
     */
    int countByOrigamiId(String origamiId);

    /**
     * Check if an origami exists by external ID.
     */
    boolean existsByOrigamiId(String origamiId);

    /**
     * Find origami items with vote count greater than specified value.
     */
    List<Origami> findByVoteCountGreaterThanAndActiveTrue(Integer voteCount);

    /**
     * Find top N origami items by vote count.
     */
    @Query("SELECT o FROM Origami o WHERE o.active = true ORDER BY o.voteCount DESC, o.createdAt ASC")
    List<Origami> findTopByVoteCount(Pageable pageable);

    /**
     * Atomically increment vote count for an origami item.
     * This method ensures thread-safe vote counting.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("UPDATE Origami o SET o.voteCount = o.voteCount + 1, o.updatedAt = CURRENT_TIMESTAMP WHERE o.id = :id")
    int incrementVoteCount(@Param("id") Long id);

    /**
     * Atomically increment vote count by origami ID.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("UPDATE Origami o SET o.voteCount = o.voteCount + 1, o.updatedAt = CURRENT_TIMESTAMP WHERE o.origamiId = :origamiId AND o.active = true")
    int incrementVoteCountByOrigamiId(@Param("origamiId") String origamiId);

    /**
     * Soft delete an origami item by setting active to false.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("UPDATE Origami o SET o.active = false, o.updatedAt = CURRENT_TIMESTAMP WHERE o.id = :id")
    int softDeleteById(@Param("id") Long id);

    /**
     * Soft delete an origami item by external ID.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("UPDATE Origami o SET o.active = false, o.updatedAt = CURRENT_TIMESTAMP WHERE o.origamiId = :origamiId")
    int softDeleteByOrigamiId(@Param("origamiId") String origamiId);

    /**
     * Bulk update origami items from catalogue service data.
     */
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Transactional
    @Query("UPDATE Origami o SET o.name = :name, o.description = :description, o.imageUrl = :imageUrl, o.updatedAt = CURRENT_TIMESTAMP WHERE o.origamiId = :origamiId")
    int updateOrigamiDetails(@Param("origamiId") String origamiId, 
                            @Param("name") String name, 
                            @Param("description") String description, 
                            @Param("imageUrl") String imageUrl);

    /**
     * Find origami items created after a specific date.
     */
    List<Origami> findByCreatedAtAfterAndActiveTrue(LocalDateTime createdAfter);

    /**
     * Get vote count statistics.
     */
    @Query("SELECT MIN(o.voteCount), MAX(o.voteCount), AVG(o.voteCount), COUNT(o) FROM Origami o WHERE o.active = true")
    Object[] getVoteCountStatistics();

    /**
     * Find origami items that need synchronization (haven't been updated recently).
     */
    @Query("SELECT o FROM Origami o WHERE o.active = true AND o.updatedAt < :threshold")
    List<Origami> findOrigamiNeedingSync(@Param("threshold") LocalDateTime threshold);

    /**
     * Custom query to find origami by name pattern (case-insensitive).
     */
    @Query("SELECT o FROM Origami o WHERE o.active = true AND LOWER(o.name) LIKE LOWER(CONCAT('%', :namePattern, '%'))")
    List<Origami> findByNameContainingIgnoreCase(@Param("namePattern") String namePattern);
}

