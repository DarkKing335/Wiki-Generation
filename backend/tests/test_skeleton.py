"""Skeleton rendering tests (FR-15, US-3.5, ADR-010).

The claim under test is ADR-010's: that a compact structural rendering carries
every architecturally meaningful fact about a type while omitting the algorithm.
So these tests assert both halves — what a skeleton *must* contain, and what it
must never contain.
"""

from __future__ import annotations

import pytest

from ai_analysis.skeleton import (
    render_annotations,
    render_class_skeleton,
    render_member,
    render_method_skeleton,
    render_signature,
    render_summary_digest,
)
from ai_analysis.tokens import count_tokens


#: Fragments that appear only inside method bodies in the sample repo.  If any
#: reaches a skeleton, the renderer has leaked an implementation.
BODY_FRAGMENTS = (
    "compareTo",
    "tokenize",
    "System.out.println",
    "ArrayList",
    "templateEngine.expand",
    "PdfWriter.fromHtml",
    "_repository.LoadAsync",
)


@pytest.fixture
def payment_processor(sample_index):
    return sample_index.build_registry()["com.acme.billing.payment.PaymentProcessor"]


@pytest.fixture
def charge_method(sample_index):
    # Epic 1 stores member names in qualified form ("PaymentProcessor.charge"),
    # so look the symbol up by FQN rather than by simple name.
    return sample_index.build_registry()["com.acme.billing.payment.PaymentProcessor.charge"]


class TestClassSkeleton:

    def test_includes_the_type_declaration(self, payment_processor, sample_index):
        text = render_class_skeleton(payment_processor, sample_index)
        assert "PaymentProcessor" in text
        assert text.startswith("Class:")

    def test_includes_annotations(self, payment_processor, sample_index):
        text = render_class_skeleton(payment_processor, sample_index)
        assert "@Service" in text

    def test_includes_implemented_interfaces(self, payment_processor, sample_index):
        text = render_class_skeleton(payment_processor, sample_index)
        assert "implements" in text
        assert "PaymentGateway" in text

    def test_includes_field_types(self, payment_processor, sample_index):
        text = render_class_skeleton(payment_processor, sample_index)
        assert "stripeClient : StripeClient" in text
        assert "minimumCharge : BigDecimal" in text

    def test_includes_method_signatures(self, payment_processor, sample_index):
        text = render_class_skeleton(payment_processor, sample_index)
        assert "charge(" in text
        assert "TransactionDto" in text

    def test_includes_docstrings(self, payment_processor, sample_index):
        text = render_class_skeleton(payment_processor, sample_index)
        assert "Doc:" in text
        assert "Charges customer cards" in text

    def test_never_emits_method_bodies(self, payment_processor, sample_index):
        text = render_class_skeleton(payment_processor, sample_index)
        for fragment in BODY_FRAGMENTS:
            assert fragment not in text, f"body fragment '{fragment}' leaked into skeleton"

    def test_is_materially_smaller_than_source(
        self, payment_processor, sample_index, sample_repo_dir
    ):
        """The whole point: a skeleton must cost a fraction of the source."""
        source = (sample_repo_dir / payment_processor.file_path).read_text(encoding="utf-8")
        text = render_class_skeleton(payment_processor, sample_index)

        assert count_tokens(text) < count_tokens(source) * 0.75

    def test_every_type_in_the_corpus_stays_body_free(self, sample_index):
        for symbol in sample_index.symbols:
            if not symbol.is_type:
                continue
            text = render_class_skeleton(symbol, sample_index)
            for fragment in BODY_FRAGMENTS:
                assert fragment not in text, (
                    f"'{fragment}' leaked into skeleton for {symbol.fully_qualified_name}"
                )


class TestDegradation:
    """Render options are the levers ``tokens.enforce_budget`` pulls."""

    def test_dropping_private_members_shrinks_the_skeleton(
        self, payment_processor, sample_index
    ):
        full = render_class_skeleton(payment_processor, sample_index, include_private=True)
        trimmed = render_class_skeleton(payment_processor, sample_index, include_private=False)

        assert "audit" in full
        assert "audit" not in trimmed
        assert len(trimmed) < len(full)

    def test_dropping_docstrings_shrinks_the_skeleton(self, payment_processor, sample_index):
        with_docs = render_class_skeleton(payment_processor, sample_index)
        without = render_class_skeleton(
            payment_processor, sample_index, include_docstrings=False
        )

        assert "Doc:" in with_docs
        assert "Doc:" not in without

    def test_docstrings_truncate_to_the_requested_length(
        self, payment_processor, sample_index
    ):
        text = render_class_skeleton(payment_processor, sample_index, doc_chars=20)
        for line in text.splitlines():
            if "Doc:" in line:
                assert len(line.split("Doc:", 1)[1].strip()) <= 20

    def test_each_step_is_no_larger_than_the_one_before(
        self, payment_processor, sample_index
    ):
        sizes = [
            count_tokens(render_class_skeleton(payment_processor, sample_index, **options))
            for options in (
                {},
                {"include_private": False},
                {"include_private": False, "doc_chars": 80},
                {"include_private": False, "include_docstrings": False},
            )
        ]
        assert sizes == sorted(sizes, reverse=True)


class TestMethodSkeleton:

    def test_names_the_declaring_type(self, charge_method, sample_index):
        text = render_method_skeleton(charge_method, sample_index)
        assert "Declared in:" in text
        assert "PaymentProcessor" in text

    def test_includes_the_signature_and_annotations(self, charge_method, sample_index):
        text = render_method_skeleton(charge_method, sample_index)
        assert "charge(" in text
        assert "@Transactional" in text

    def test_records_the_source_range_without_reading_it(self, charge_method, sample_index):
        """The pointer is present so the model can *ask* for the body (§8)."""
        text = render_method_skeleton(charge_method, sample_index)
        assert (
            f"Source: {charge_method.file_path}:"
            f"{charge_method.range.start_line}-{charge_method.range.end_line}"
        ) in text

    def test_never_emits_the_body(self, sample_index):
        for symbol in sample_index.symbols:
            if not symbol.is_callable:
                continue
            text = render_method_skeleton(symbol, sample_index)
            for fragment in BODY_FRAGMENTS:
                assert fragment not in text, (
                    f"'{fragment}' leaked into skeleton for {symbol.fully_qualified_name}"
                )


class TestRenderHelpers:

    def test_annotations_render_with_arguments(self, sample_index):
        controller = sample_index.build_registry()["Acme.Identity.Controllers.UserController"]
        text = render_annotations(controller)
        assert "@ApiController" in text

    def test_signature_shortens_qualified_types(self, charge_method, sample_index):
        text = render_signature(charge_method)
        assert "java.math" not in text
        assert "com.acme" not in text

    def test_member_renders_csharp_property_accessors(self, sample_index):
        version = sample_index.build_registry()[
            "Acme.Identity.Controllers.UserController.Version"
        ]
        text = render_member(version)
        assert "Version :" in text

    def test_summary_digest_lists_children_by_name(self):
        text = render_summary_digest([
            ("payment-service", "Charges cards via Stripe."),
            ("invoice-service", "Renders invoice PDFs."),
        ])
        assert text.splitlines() == [
            "- payment-service: Charges cards via Stripe.",
            "- invoice-service: Renders invoice PDFs.",
        ]

    def test_summary_digest_collapses_whitespace(self):
        text = render_summary_digest([("a", "line one\n   line two")])
        assert text == "- a: line one line two"
