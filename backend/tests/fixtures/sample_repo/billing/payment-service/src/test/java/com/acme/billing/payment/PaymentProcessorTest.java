package com.acme.billing.payment;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import java.math.BigDecimal;

/**
 * Unit tests for {@link PaymentProcessor}.
 */
public class PaymentProcessorTest {

    private PaymentProcessor processor;

    @BeforeEach
    public void setUp() {
        this.processor = new PaymentProcessor(new StripeClient());
    }

    @Test
    public void chargeRejectsAmountsBelowMinimum() {
        TransactionDto dto = new TransactionDto(new BigDecimal("0.10"));
        boolean threw = false;
        try {
            processor.charge(dto);
        } catch (PaymentException expected) {
            threw = true;
        }
        assert threw;
    }

    @Test
    public void minimumChargeIsFiftyCents() {
        assert processor.getMinimumCharge().equals(new BigDecimal("0.50"));
    }
}
