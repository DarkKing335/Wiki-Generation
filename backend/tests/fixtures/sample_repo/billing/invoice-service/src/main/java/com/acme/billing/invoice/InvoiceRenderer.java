package com.acme.billing.invoice;

import org.springframework.stereotype.Service;
import java.util.List;

/**
 * Renders invoices to PDF for delivery to customers.
 */
@Service
public class InvoiceRenderer {

    private final TemplateEngine templateEngine;

    public InvoiceRenderer(TemplateEngine templateEngine) {
        this.templateEngine = templateEngine;
    }

    /**
     * Render one invoice into a PDF byte array.
     */
    public byte[] render(Invoice invoice) {
        String html = templateEngine.expand("invoice.html", invoice);
        byte[] pdf = PdfWriter.fromHtml(html);
        if (pdf.length == 0) {
            throw new IllegalStateException("Rendered an empty invoice");
        }
        return pdf;
    }

    public int countLineItems(Invoice invoice) {
        return invoice.getLineItems().size();
    }
}
