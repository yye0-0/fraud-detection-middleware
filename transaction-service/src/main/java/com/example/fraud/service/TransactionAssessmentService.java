package com.example.fraud.service;

import com.example.fraud.domain.Decision;
import com.example.fraud.domain.FraudAssessment;
import com.example.fraud.domain.TransactionRequest;
import com.example.fraud.persistence.AssessmentEntity;
import com.example.fraud.persistence.AssessmentRepository;
import com.example.fraud.rules.FraudRuleEngine;
import java.time.Instant;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TransactionAssessmentService {
    private final FraudRuleEngine ruleEngine;
    private final MlRiskClient riskClient;
    private final DecisionPolicy decisionPolicy;
    private final AssessmentRepository repository;
    private final AssessmentPublisher publisher;

    public TransactionAssessmentService(FraudRuleEngine ruleEngine, MlRiskClient riskClient,
            DecisionPolicy decisionPolicy, AssessmentRepository repository, AssessmentPublisher publisher) {
        this.ruleEngine = ruleEngine;
        this.riskClient = riskClient;
        this.decisionPolicy = decisionPolicy;
        this.repository = repository;
        this.publisher = publisher;
    }

    @Transactional
    public FraudAssessment assess(TransactionRequest request) {
        List<String> triggeredRules = ruleEngine.evaluate(request);
        MlRiskClient.ScoreResult score = riskClient.score(request, triggeredRules);
        Decision decision = decisionPolicy.decide(score.probability(), score.reviewThreshold(), triggeredRules);
        String reason = decision == Decision.APPROVE
                ? "No configured risk threshold was reached"
                : "One or more risk signals require analyst review";
        FraudAssessment result = new FraudAssessment(request.transactionId(), decision, score.probability(),
                score.modelVersion(), triggeredRules, score.signals(), reason, Instant.now());
        repository.save(new AssessmentEntity(result));
        publisher.publish(result);
        return result;
    }
}
