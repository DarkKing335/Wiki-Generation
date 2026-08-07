package com.acme.billing.payment;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.math.BigDecimal;
import java.util.List;

/**
 * Charges customer cards through the configured payment gateway.
 */
@Service
public class PaymentProcessor implements PaymentGateway {

    private final StripeClient stripeClient;
    private final BigDecimal minimumCharge;

    public PaymentProcessor(StripeClient stripeClient) {
        this.stripeClient = stripeClient;
        this.minimumCharge = new BigDecimal("0.50");
    }

    /**
     * Charge a single transaction, rejecting amounts below the gateway minimum.
     */
    @Transactional
    public PaymentResult charge(TransactionDto dto) throws PaymentException {
        if (dto.getAmount().compareTo(minimumCharge) < 0) {
            throw new PaymentException("Amount below gateway minimum");
        }
        String token = stripeClient.tokenize(dto.getCardNumber());
        PaymentResult result = stripeClient.submit(token, dto.getAmount());
        audit(result);
        return result;
    }

    /**
     * Charge several transactions, stopping at the first failure.
     */
    public List<PaymentResult> chargeAll(List<TransactionDto> transactions) throws PaymentException {
        List<PaymentResult> results = new java.util.ArrayList<>();
        for (TransactionDto dto : transactions) {
            results.add(charge(dto));
        }
        return results;
    }

    private void audit(PaymentResult result) {
        System.out.println("audit " + result);
    }

    public BigDecimal getMinimumCharge() {
        return minimumCharge;
    }
}
