package com.example.fraud.service;

import com.example.fraud.domain.Decision;
import java.math.BigDecimal;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class DecisionPolicy {
    public Decision decide(BigDecimal probability, BigDecimal reviewThreshold, List<String> triggeredRules) {
        if (probability.compareTo(reviewThreshold) >= 0 || !triggeredRules.isEmpty()) return Decision.REVIEW;
        return Decision.APPROVE;
    }
}
