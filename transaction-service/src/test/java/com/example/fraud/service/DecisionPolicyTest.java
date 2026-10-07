package com.example.fraud.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import com.example.fraud.domain.Decision;

class DecisionPolicyTest {
    private final DecisionPolicy policy = new DecisionPolicy();

    @Test void routesToReviewAtConfiguredThreshold() {
        assertEquals(Decision.REVIEW, policy.decide(new BigDecimal("0.90"), new BigDecimal("0.90"), List.of()));
    }

    @Test void reviewsRuleSignalEvenWhenScoreIsLow() {
        assertEquals(Decision.REVIEW, policy.decide(new BigDecimal("0.10"), new BigDecimal("0.90"), List.of("HIGH_AMOUNT")));
    }

    @Test void approvesWhenNoSignalsReachThreshold() {
        assertEquals(Decision.APPROVE, policy.decide(new BigDecimal("0.49"), new BigDecimal("0.90"), List.of()));
    }
}
