package com.example.voting.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.example.voting.model.Origami;
import com.example.voting.repository.OrigamiRepository;

import java.util.List;
import java.util.Optional;

@Service
public class OrigamiService {

    @Autowired
    private OrigamiRepository origamiRepository;

    public List<Origami> getAllOrigami() {
        return origamiRepository.findByActiveTrue();
    }

    public Optional<Origami> getOrigamiById(Long id) {
        return origamiRepository.findById(id);
    }

    public Optional<Origami> getOrigamiByOrigamiId(String origamiId) {
        return origamiRepository.findByOrigamiIdAndActiveTrue(origamiId);
    }

    public Origami saveOrUpdateOrigami(Origami origami) {
        return origamiRepository.save(origami);
    }

    public int getVotes(String origamiId) {
        return origamiRepository.findByOrigamiId(origamiId)
                .map(Origami::getVoteCount)
                .orElse(0);
    }

    public boolean incrementVote(Long id) {
        int updated = origamiRepository.incrementVoteCount(id);
        return updated > 0;
    }
}
