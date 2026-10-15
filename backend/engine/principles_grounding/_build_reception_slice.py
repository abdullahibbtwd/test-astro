#!/usr/bin/env python3
"""Author syn_reception_slice.json — 23 reception principles (interaction: reception).
Neutral reframes of the classical reception technique; rule text uses {RECEIVER}/
{RECEIVED} person tokens that ground_relationship.py substitutes at bind time."""
import json


def rec(pid, tags, rule, judgment, syn, notes=None):
    return {"principle_id": pid, "domain": "relationship", "topic_tags": tags,
            "rule": rule,
            "conditions": ["cross-chart reception between a significator of each person"],
            "judgment": judgment, "attribution_in_text": None, "notes": notes,
            "tradition": "traditional",
            "synastry": dict(interaction="reception", **syn)}


R = [
 rec("syn-reception-general", ["synastry", "reception"],
     "When a planet of {RECEIVED} occupies a sign in the dignity of a planet of {RECEIVER}, {RECEIVER} receives {RECEIVED}: {RECEIVER} tends to welcome, accommodate, and support {RECEIVED} in the matters signified by the received planet, easing cooperation even between otherwise dissimilar charts.",
     "A supportive, welcoming current runs from {RECEIVER} toward {RECEIVED}.", {"grade": "any"}),
 rec("syn-reception-grade-domicile", ["synastry", "reception", "domicile"],
     "When {RECEIVED}'s planet sits in a sign {RECEIVER}'s planet rules by domicile, {RECEIVER} receives {RECEIVED} into home ground - the strongest welcome; {RECEIVER} takes natural responsibility for {RECEIVED} and offers durable support in the received planet's affairs.",
     "Strong, stable welcome and care from {RECEIVER} to {RECEIVED}.", {"grade": "domicile"}),
 rec("syn-reception-grade-exaltation", ["synastry", "reception", "exaltation"],
     "When {RECEIVED}'s planet sits in the exaltation of {RECEIVER}'s planet, {RECEIVER} esteems and elevates {RECEIVED}: {RECEIVER} admires and encourages {RECEIVED} in the received planet's affairs, though the regard can be idealized.",
     "{RECEIVER} honors and lifts up {RECEIVED}.", {"grade": "exaltation"}),
 rec("syn-reception-grade-triplicity", ["synastry", "reception", "triplicity"],
     "When {RECEIVED}'s planet falls in the triplicity of {RECEIVER}'s planet, {RECEIVER} offers {RECEIVED} steady, companionable support grounded in shared temperament and values.",
     "Comfortable, values-based support from {RECEIVER}.", {"grade": "triplicity"}),
 rec("syn-reception-grade-bound", ["synastry", "reception", "bound"],
     "When {RECEIVED}'s planet falls in the bounds of {RECEIVER}'s planet, {RECEIVER} lends {RECEIVED} limited, situational assistance in the received planet's affairs - real but minor.",
     "Minor, conditional help from {RECEIVER}.", {"grade": "bound"}, "minor grade; low weight"),
 rec("syn-reception-grade-face", ["synastry", "reception", "face"],
     "When {RECEIVED}'s planet falls in the face of {RECEIVER}'s planet, {RECEIVER} shows {RECEIVED} only faint, surface-level goodwill in the received planet's affairs - the weakest reception.",
     "Faint, superficial goodwill from {RECEIVER}.", {"grade": "face"}, "weakest grade; do not overweight"),
 rec("syn-reception-mutual", ["synastry", "reception", "mutual"],
     "When each person's planet occupies a sign the other's planet rules, the two mutually receive: {RECEIVER} and {RECEIVED} accommodate and support one another reciprocally, a strong sign of workable give-and-take.",
     "Reciprocal welcome and mutual accommodation.", {"grade": "any", "mutual": True}),
 rec("syn-reception-mutual-domicile-exaltation", ["synastry", "reception", "mutual", "domicile", "exaltation"],
     "When two planets, one from each chart, each sit in the other's domicile or exaltation, the reception is mutual and strong: {RECEIVER} and {RECEIVED} each feel understood and cared for by the other in these matters and readily meet each other's needs.",
     "Strong, balanced mutual reception - a major supportive contact.", {"grade": "any", "mutual": True},
     "strict mutual reception (both at domicile/exaltation)"),
 rec("syn-reception-venus-mars-mutual", ["synastry", "reception", "mutual", "Venus", "Mars"],
     "When {RECEIVER}'s Venus and {RECEIVED}'s Mars each occupy the other's dignity, affection and desire are mutually received: attraction is reciprocated and the affectionate and erotic registers align.",
     "Reciprocated attraction and desire.", {"mutual": True, "receiver_point": "Venus", "received_point": "Mars"}),
 rec("syn-reception-receiver-benefic", ["synastry", "reception", "benefic"],
     "When the receiving planet of {RECEIVER} is a benefic, the welcome extended to {RECEIVED} is warm, generous, and protective in the received planet's affairs.",
     "Warm, generous support from {RECEIVER}.", {"receiver_class": "benefic"}),
 rec("syn-reception-receiver-malefic", ["synastry", "reception", "malefic"],
     "When the receiving planet of {RECEIVER} is a malefic, {RECEIVER} still receives {RECEIVED}, but the support is demanding or disciplinary - help given through challenge, structure, or pressure.",
     "Support from {RECEIVER} arrives through demand or discipline.", {"receiver_class": "malefic"}),
 rec("syn-reception-receiver-luminary", ["synastry", "reception", "luminary"],
     "When the receiving planet of {RECEIVER} is a luminary, the welcome touches {RECEIVER}'s core identity or emotional life: {RECEIVER} receives {RECEIVED} into central, personally significant ground.",
     "{RECEIVER} welcomes {RECEIVED} at the level of identity or feeling.", {"receiver_class": "luminary"}),
 rec("syn-reception-receiver-debilitated", ["synastry", "reception", "debility"],
     "When {RECEIVER}'s receiving planet is itself in detriment or fall, the welcome to {RECEIVED} is willing but under-resourced: {RECEIVER} wishes to support {RECEIVED} but is hampered in the received planet's affairs.",
     "Willing but weakened support from {RECEIVER}.", {"receiver_debilitated": True}),
 rec("syn-reception-received-ascendant-ruler", ["synastry", "reception", "ascendant ruler"],
     "When the received planet is {RECEIVED}'s ascendant ruler, {RECEIVER} receives {RECEIVED}'s very selfhood and vitality - {RECEIVER} supports who {RECEIVED} fundamentally is.",
     "{RECEIVER} affirms {RECEIVED}'s core self.", {"received_role": "ascendant_ruler"}),
 rec("syn-reception-received-seventh-ruler", ["synastry", "reception", "seventh ruler"],
     "When the received planet is {RECEIVED}'s seventh-house ruler, the reception bears directly on partnership: {RECEIVER} accommodates {RECEIVED}'s relational needs and expectations of a partner.",
     "Reception falls squarely on partnership matters.", {"received_role": "seventh_ruler"}),
 rec("syn-reception-venus-receives", ["synastry", "reception", "Venus"],
     "When {RECEIVER}'s Venus is the receiving planet, {RECEIVER} meets {RECEIVED} with affection, esteem, and a wish to please in the received planet's affairs.",
     "{RECEIVER} extends affection and esteem to {RECEIVED}.", {"receiver_point": "Venus"}),
 rec("syn-reception-mars-receives", ["synastry", "reception", "Mars"],
     "When {RECEIVER}'s Mars is the receiving planet, {RECEIVER} energizes and defends {RECEIVED} in the received planet's affairs, though the support can be forceful or contentious.",
     "{RECEIVER} energizes and protects {RECEIVED}, sometimes forcefully.", {"receiver_point": "Mars"}),
 rec("syn-reception-saturn-receives", ["synastry", "reception", "Saturn"],
     "When {RECEIVER}'s Saturn is the receiving planet, {RECEIVER} offers {RECEIVED} structure, commitment, and duty - a sober, lasting form of care that can also feel restrictive.",
     "{RECEIVER} supports {RECEIVED} through commitment and structure.", {"receiver_point": "Saturn"}),
 rec("syn-reception-jupiter-receives", ["synastry", "reception", "Jupiter"],
     "When {RECEIVER}'s Jupiter is the receiving planet, {RECEIVER} is generous and expansive toward {RECEIVED}, offering encouragement, opportunity, and faith in the received planet's affairs.",
     "{RECEIVER} encourages and expands {RECEIVED}'s prospects.", {"receiver_point": "Jupiter"}),
 rec("syn-reception-moon-received", ["synastry", "reception", "Moon"],
     "When {RECEIVED}'s Moon is the received planet, it is {RECEIVED}'s emotional nature and needs that are welcomed: {RECEIVER} provides {RECEIVED} a sense of emotional safety and belonging.",
     "{RECEIVED} feels emotionally held by {RECEIVER}.", {"received_point": "Moon"}),
 rec("syn-reception-sun-received", ["synastry", "reception", "Sun"],
     "When {RECEIVED}'s Sun is the received planet, {RECEIVED}'s identity and creative will are welcomed: {RECEIVER} affirms and makes room for {RECEIVED}'s self-expression.",
     "{RECEIVER} affirms {RECEIVED}'s identity and will.", {"received_point": "Sun"}),
 rec("syn-reception-domicile-benefic", ["synastry", "reception", "domicile", "benefic"],
     "When a benefic of {RECEIVER} receives {RECEIVED}'s planet into its own domicile, the welcome is both strong and kind - reliable, warm, protective support in the received planet's affairs.",
     "Reliable and warm support from {RECEIVER}.", {"grade": "domicile", "receiver_class": "benefic"}),
 rec("syn-reception-exaltation-luminary", ["synastry", "reception", "exaltation", "luminary"],
     "When a luminary of {RECEIVER} receives {RECEIVED}'s planet by exaltation, {RECEIVER} holds {RECEIVED} in high personal regard, elevating {RECEIVED} within {RECEIVER}'s sense of self or emotional world.",
     "{RECEIVER} deeply esteems {RECEIVED}.", {"grade": "exaltation", "receiver_class": "luminary"}),
]

assert len(R) == 23, len(R)
with open("syn_reception_slice.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(R, fh, ensure_ascii=False, indent=1)
print("wrote syn_reception_slice.json:", len(R), "records")
