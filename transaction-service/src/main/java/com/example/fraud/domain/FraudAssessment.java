package com.example.fraud.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public record FraudAssessment(
        String transactionId,
        Decision decision,
        BigDecimal fraudProbability,
        String modelVersion,
        List<String> triggeredRules,
        List<String> modelSignals,
        String reason,
        Instant assessedAt
) {}
