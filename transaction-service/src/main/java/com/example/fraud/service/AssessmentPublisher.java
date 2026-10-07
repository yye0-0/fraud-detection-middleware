package com.example.fraud.service;

import com.example.fraud.domain.FraudAssessment;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class AssessmentPublisher {
    private final KafkaTemplate<String, FraudAssessment> kafka;
    private final String topic;

    public AssessmentPublisher(KafkaTemplate<String, FraudAssessment> kafka,
                               @Value("${app.kafka.topic}") String topic) {
        this.kafka = kafka;
        this.topic = topic;
    }

    public void publish(FraudAssessment assessment) {
        kafka.send(topic, assessment.transactionId(), assessment);
    }
}
