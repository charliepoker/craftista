package com.example.voting.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import java.time.LocalDateTime;

/**
 * Origami entity representing origami products in the voting system.
 * 
 * Enhanced with proper JPA annotations, validation, and audit fields
 * for production-ready database operations.
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
@EqualsAndHashCode(of = "id")
@Entity
@Table(name = "origami", indexes = {
    @Index(name = "idx_origami_active", columnList = "active"),
    @Index(name = "idx_origami_external_id", columnList = "origami_id"),
    @Index(name = "idx_origami_vote_count", columnList = "vote_count"),
    @Index(name = "idx_origami_created_at", columnList = "created_at")
})
public class Origami {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Long id;

    @NotBlank(message = "Origami ID cannot be blank")
    @Size(max = 50, message = "Origami ID cannot exceed 50 characters")
    @Column(name = "origami_id", unique = true, nullable = false, length = 50)
    private String origamiId;

    @NotBlank(message = "Name cannot be blank")
    @Size(max = 255, message = "Name cannot exceed 255 characters")
    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "image_url", length = 500)
    private String imageUrl;

    @NotNull(message = "Vote count cannot be null")
    @PositiveOrZero(message = "Vote count must be zero or positive")
    @Column(name = "vote_count", nullable = false)
    @Builder.Default
    private Integer voteCount = 0;

    @NotNull(message = "Active status cannot be null")
    @Column(name = "active", nullable = false)
    @Builder.Default
    private Boolean active = true;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @Version
    @Column(name = "version")
    private Long version;

    /**
     * Maps the external 'id' field from JSON to internal 'origamiId' field.
     * This maintains backward compatibility with existing API contracts.
     */
    @JsonProperty("id")
    public void setOrigamiIdFromJson(String id) {
        this.origamiId = id;
    }

    @JsonProperty("id")
    public String getOrigamiIdForJson() {
        return this.origamiId;
    }

    /**
     * Maps the 'votes' field from JSON to internal 'voteCount' field.
     * This maintains backward compatibility with existing API contracts.
     */
    @JsonProperty("votes")
    public void setVotesFromJson(Integer votes) {
        this.voteCount = votes != null ? votes : 0;
    }

    @JsonProperty("votes")
    public Integer getVotesForJson() {
        return this.voteCount;
    }

    /**
     * Increment the vote count atomically.
     * This method should be used in conjunction with database-level atomic operations.
     */
    public void incrementVoteCount() {
        this.voteCount = (this.voteCount != null ? this.voteCount : 0) + 1;
    }

    /**
     * Pre-persist callback to ensure default values are set.
     */
    @PrePersist
    protected void onCreate() {
        if (this.voteCount == null) {
            this.voteCount = 0;
        }
        if (this.active == null) {
            this.active = true;
        }
    }

    /**
     * Pre-update callback to update the timestamp.
     */
    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = LocalDateTime.now();
    }
}

