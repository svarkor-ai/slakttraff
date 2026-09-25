"""Seed the persons table with the Släktträff family tree.

Runs once on startup when the table is empty so the frontend tree renders
from API data on a fresh database. Family data mirrors the original static
page (teddy/index.html before the API wiring).
"""
from app.database import SessionLocal
from app.models.person import Person
from app.schemas.enums import RsvpStatus

# (key, name, generation, role, relation, description, parent keys)
FAMILY = [
    ("erik", "Erik", 1, "Grundare", "Familiens äldste", "Släktens grundare. Har 2 barn.", []),
    ("gosta", "Gösta", 1, "Grundare", "Familiens äldste", "En av de sju grundarna. Har 1 barn.", []),
    ("gerty", "Gerty", 1, "Grundare", "Familiens äldste", "En av de sju grundarna. Har 2 barn.", []),
    ("nanna", "Nanna", 1, "Grundare", "Familiens äldste", "En av de sju grundarna. Har 3 barn: Lars, Lena och Frank.", []),
    ("stig", "Stig", 1, "Grundare", "Familiens äldste", "En av de sju grundarna. Har 5 barn.", []),
    ("ulla", "Ulla", 1, "Grundare", "Familiens äldste", "En av de sju grundarna. Har 1 barn.", []),
    ("britt", "Britt", 1, "Grundare", "Familiens äldste", "En av de sju grundarna. Har 1 barn.", []),
    ("anna", "Anna", 2, "Barn", "Barn till Erik", "Äldsta barnet till Erik.", ["erik"]),
    ("magnus", "Magnus", 2, "Barn", "Barn till Erik", "Andra barnet till Erik.", ["erik"]),
    ("lisa", "Lisa", 2, "Barn", "Barn till Gösta", "Endaste barnet till Gösta.", ["gosta"]),
    ("johan", "Johan", 2, "Barn", "Barn till Gerty", "Äldsta barnet till Gerty.", ["gerty"]),
    ("karin", "Karin", 2, "Barn", "Barn till Gerty", "Andra barnet till Gerty.", ["gerty"]),
    ("lars", "Lars", 2, "Barn", "Barn till Nanna", "Äldsta barnet till Nanna. Har 2 barn: Aron och Sandra.", ["nanna"]),
    ("lena", "Lena", 2, "Barn", "Barn till Nanna", "Mellankind till Nanna. Har 2 barn: Elin och Malin.", ["nanna"]),
    ("frank", "Frank", 2, "Barn", "Barn till Nanna", "Yngsta barnet till Nanna. Har 1 barn: Emelie.", ["nanna"]),
    ("emma", "Emma", 2, "Barn", "Barn till Stig", "Äldsta barnet till Stig.", ["stig"]),
    ("oskar", "Oskar", 2, "Barn", "Barn till Stig", "Andra barnet till Stig.", ["stig"]),
    ("maja", "Maja", 2, "Barn", "Barn till Stig", "Tredje barnet till Stig.", ["stig"]),
    ("linus", "Linus", 2, "Barn", "Barn till Stig", "Fjärde barnet till Stig.", ["stig"]),
    ("elliot", "Elliot", 2, "Barn", "Barn till Stig", "Yngsta barnet till Stig.", ["stig"]),
    ("alva", "Alva", 2, "Barn", "Barn till Ulla", "Endaste barnet till Ulla.", ["ulla"]),
    ("felix", "Felix", 2, "Barn", "Barn till Britt", "Endaste barnet till Britt.", ["britt"]),
    ("aron", "Aron", 3, "Barnbarn", "Barn till Lars", "Äldsta barnet till Lars.", ["lars"]),
    ("sandra", "Sandra", 3, "Barnbarn", "Barn till Lars", "Andra barnet till Lars.", ["lars"]),
    ("elin", "Elin", 3, "Barnbarn", "Barn till Lena", "Äldsta barnet till Lena. Har 2 barn: Noa och Freja.", ["lena"]),
    ("malin", "Malin", 3, "Barnbarn", "Barn till Lena", "Andra barnet till Lena. Har 3 barn: Amelia, Emmy och Anton.", ["lena"]),
    ("emelie", "Emelie", 3, "Barnbarn", "Barn till Frank", "Endaste barnet till Frank.", ["frank"]),
    ("wilma", "Wilma", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("arvid", "Arvid", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("sigrid", "Sigrid", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("lucas", "Lucas", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("astrid", "Astrid", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("noah", "Noah", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("ingrid", "Ingrid", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("freja", "Freja", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("elias", "Elias", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("ella", "Ella", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("axel", "Axel", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("lykke", "Lykke", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("julius", "Julius", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("borgny", "Borgny", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("ida", "Ida", 3, "Barnbarn", "Barnbarn", "Barnbarn i släkten.", []),
    ("liam", "Liam", 4, "Barnbarnsbarn", "Barn till Aron", "Äldsta barnet till Aron.", ["aron"]),
    ("oliver", "Oliver", 4, "Barnbarnsbarn", "Barn till Aron", "Andra barnet till Aron.", ["aron"]),
    ("anny", "Anny", 4, "Barnbarnsbarn", "Barn till Sandra", "Äldsta barnet till Sandra.", ["sandra"]),
    ("mira", "Mira", 4, "Barnbarnsbarn", "Barn till Sandra", "Mellankind till Sandra.", ["sandra"]),
    ("maja_g4", "Maja", 4, "Barnbarnsbarn", "Barn till Sandra", "Yngsta barnet till Sandra.", ["sandra"]),
    ("noa", "Noa", 4, "Barnbarnsbarn", "Barn till Elin", "Äldsta barnet till Elin.", ["elin"]),
    ("freja_g4", "Freja", 4, "Barnbarnsbarn", "Barn till Elin", "Andra barnet till Elin.", ["elin"]),
    ("amelia", "Amelia", 4, "Barnbarnsbarn", "Barn till Malin", "Äldsta barnet till Malin.", ["malin"]),
    ("emmy", "Emmy", 4, "Barnbarnsbarn", "Barn till Malin", "Andra barnet till Malin.", ["malin"]),
    ("anton", "Anton", 4, "Barnbarnsbarn", "Barn till Malin", "Tredje barnet till Malin.", ["malin"]),
    ("ludvig", "Ludvig", 4, "Barnbarnsbarn", "Barnbarnsbarn", "Barnbarnsbarn i släkten.", []),
    ("signe", "Signe", 4, "Barnbarnsbarn", "Barnbarnsbarn", "Barnbarnsbarn i släkten.", []),
    ("ragnar", "Ragnar", 4, "Barnbarnsbarn", "Barnbarnsbarn", "Barnbarnsbarn i släkten.", []),
    ("hilma", "Hilma", 4, "Barnbarnsbarn", "Barnbarnsbarn", "Barnbarnsbarn i släkten.", []),
    ("ingvar", "Ingvar", 4, "Barnbarnsbarn", "Barnbarnsbarn", "Barnbarnsbarn i släkten.", []),
    ("marianne", "Marianne", 4, "Barnbarnsbarn", "Barnbarnsbarn", "Barnbarnsbarn i släkten.", []),
    ("bo", "Bo", 4, "Barnbarnsbarn", "Barnbarnsbarn", "Barnbarnsbarn i släkten.", []),
    ("alice", "Alice", 5, "Barnbarnsbarnsbarn", "Barnbarnsbarnsbarn", "Yngsta generationen i släkten.", []),
    ("nils", "Nils", 5, "Barnbarnsbarnsbarn", "Barnbarnsbarnsbarn", "Yngsta generationen i släkten.", []),
    ("stina", "Stina", 5, "Barnbarnsbarnsbarn", "Barnbarnsbarnsbarn", "Yngsta generationen i släkten.", []),
]


def seed_persons_if_empty() -> int:
    """Insert the family tree once, when the persons table is empty.

    Returns the number of persons inserted (0 when the table already has data).
    """
    db = SessionLocal()
    try:
        if db.query(Person).count() > 0:
            return 0
        ids = {}
        for key, name, gen, role, relation, desc, _parents in FAMILY:
            person = Person(
                name=name,
                generation=gen,
                role=role,
                relation=relation,
                description=desc,
                parents=[],
                children=[],
                spouses=[],
                rsvp_status=RsvpStatus.PENDING.value,
                rsvp_token=key,  # legacy column, no longer gated on
            )
            db.add(person)
            db.flush()
            ids[key] = person.id
        for key, _name, _gen, _role, _rel, _desc, parents in FAMILY:
            person = db.query(Person).filter(Person.id == ids[key]).first()
            person.parents = [ids[p] for p in parents]
            for p in parents:
                child = db.query(Person).filter(Person.id == ids[p]).first()
                child.children = list(child.children or []) + [ids[key]]
        db.commit()
        return len(FAMILY)
    finally:
        db.close()
