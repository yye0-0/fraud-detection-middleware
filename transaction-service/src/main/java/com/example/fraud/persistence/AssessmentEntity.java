package com.example.fraud.persistence;

import com.example.fraud.domain.FraudAssessment;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "fraud_assessments")
public class AssessmentEntity {
    @Id
    @Column(name = "transaction_id", nullable = false, length = 100)
    private String transactionId;
    @Column(nullable = false, length = 20) private String decision;
    @Column(name = "fraud_probability", nullable = false) private double fraudProbability;
    @Column(name = "model_version", length = 80) private String modelVersion;
    @Column(name = "triggered_rules", length = 1000) private String triggeredRules;
    @Column(name = "model_signals", length = 1000) private String modelSignals;
    @Column(length = 300) private String reason;
    @Column(name = "assessed_at", nullable = false) private Instant assessedAt;

    protected AssessmentEntity() {}

    public AssessmentEntity(FraudAssessment assessment) {
        this.transactionId = assessment.transactionId();
        this.decision = assessment.decision().name();
        this.fraudProbability = assessment.fraudProbability().doubleValue();
        this.modelVersion = assessment.modelVersion();
        this.triggeredRules = String.join(",", assessment.triggeredRules());
        this.modelSignals = String.join(",", assessment.modelSignals());
        this.reason = assessment.reason();
        this.assessedAt = assessment.assessedAt();
    }
}
