"""A small, auditable multinomial Naive Bayes intent model trained locally.

This is statistical intent classification, not a generative LLM or financial advisor.
It selects deterministic investigation tools and never invents ledger facts.
"""
import math
import re
from collections import Counter

TRAINING = {
    "refunds": ["find refunds missing from merchant books", "show returned money and refund mismatch", "investigate refunded payment difference", "which reimbursement records are wrong", "check refunds against ledger", "explain refund reconciliation"],
    "captures": ["show captured payments with missing money", "investigate capture mismatch", "check unpaid orders and pending payments", "find cash collected versus invoices", "explain capture reconciliation", "which invoice payment was incomplete"],
    "replays": ["find duplicate webhook deliveries", "why repeated events did not change balance", "show replayed notifications", "check duplicate transaction evidence", "investigate event replays", "were any webhook events counted twice"],
    "currency": ["show foreign currency mismatch", "find wrong currencies", "check dollar versus euro transactions", "investigate currency differences", "which payments have incompatible currency", "show currency validation failures"],
    "overview": ["summarize reconciliation results", "show all issues", "give overall audit summary", "what needs review today", "list every flagged order", "overview of merchant books"]
}
STOP = set("a an the i me my to for with and or of in is are was were did any have has which why what how show find check explain investigate against give from all every today".split())
def tokens(text):
    return [t for t in re.findall(r"[a-z]+", text.lower()) if t not in STOP]

class IntentModel:
    def __init__(self):
        self.counts = {label: Counter(t for phrase in phrases for t in tokens(phrase)) for label, phrases in TRAINING.items()}
        self.vocab = set().union(*(set(c) for c in self.counts.values()))
    def classify(self, query):
        terms = tokens(query)
        known = [t for t in terms if t in self.vocab]
        scores = {}
        for label, counts in self.counts.items():
            total = sum(counts.values()) + len(self.vocab)
            scores[label] = sum(math.log((counts[t] + 1) / total) for t in known)
        ordered = sorted(scores, key=scores.get, reverse=True)
        best = ordered[0]
        margin = scores[best] - scores[ordered[1]]
        shifted = {k: math.exp(v - scores[best]) for k, v in scores.items()}
        support = shifted[best] / sum(shifted.values())
        abstain = not known or margin < 0.5 or support < 0.4
        return {"intent": None if abstain else best, "model": "local multinomial Naive Bayes",
                "support": round(support, 3), "margin": round(margin, 3), "abstained": abstain,
                "matched_terms": sorted(set(known)), "note": "Model support is not calibrated probability; synthetic training examples only."}

MODEL = IntentModel()
FILTERS = {"refunds": {"REFUND_GAP", "ORPHAN_REFUND", "OVER_REFUND"},
           "captures": {"CAPTURE_GAP", "PENDING"}, "replays": {"REPLAY", "EVENT_CONFLICT"}, "currency": {"CURRENCY"}}
def investigate(query, report):
    prediction = MODEL.classify(query)
    if prediction["abstained"]:
        return {"prediction": prediction, "answer": "I could not confidently select an investigation. Ask about refunds, captures, duplicate events, currencies, or an overall summary.", "cases": []}
    intent = prediction["intent"]
    cases = report["cases"] if intent == "overview" else [c for c in report["cases"] if any(i["code"] in FILTERS[intent] for i in c["issues"])]
    facts = [{"invoice": c["invoice"], "order_id": c["order_id"], "currency": c["currency"],
              "difference_minor": c["difference_minor"], "issues": c["issues"], "resource_ids": [r["id"] for r in c["evidence"]]} for c in cases]
    return {"prediction": prediction, "answer": f"Selected {len(cases)} order(s) for {intent}. The amounts and evidence below come directly from the reconciler. Proposed actions need human review.", "cases": facts}
