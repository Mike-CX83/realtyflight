"""Context enrichment (D13): address → real property boundary, as PROPOSALS.

Iron rule (TODO D13, doc 13): external data widens the LLM's CONTEXT, never
its AUTHORITY. Everything this package produces lands on the operator's
confirmation screen as a proposal; the validator judges the plan against what
the human ratified — same 14 rules, no bypass, no new trust.
"""

from context.enrich import PropertyProposal, propose_property
from context.geocode import GeocodeResult, LookupFailed, geocode
from context.parcel import ArcGISParcelProvider, ParcelResult

__all__ = [
    "ArcGISParcelProvider",
    "GeocodeResult",
    "LookupFailed",
    "ParcelResult",
    "PropertyProposal",
    "geocode",
    "propose_property",
]
