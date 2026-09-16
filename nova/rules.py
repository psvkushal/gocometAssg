"""Load customer-written rules without interpreting or rewriting them."""

from pathlib import Path

from nova.schemas import CustomerRules


def load_customer_rules(path: str | Path) -> CustomerRules:
    """Read UTF-8 rules; file/encoding errors propagate and blank rules are rejected."""
    source = Path(path).expanduser().resolve()
    text = source.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"Customer rule file is blank: {source}")
    return CustomerRules(text=text, source=str(source))
