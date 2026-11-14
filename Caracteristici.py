"""Caracteristicile necesare pentru fiecare astronaut.

Lista provine din README.md ("Caracteristicile necesare").
Fiecare caracteristică are limite minime și maxime plauzibile pentru un om adult,
iar valorile introduse sunt verificate și între ele (coerență).
"""

import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

CALE_DB = Path(__file__).with_name("astronauti.db")
LUNGIME_MAXIMA_NUME = 50

# Diferența maximă acceptată între IMC introdus și IMC calculat din masă și înălțime.
TOLERANTA_IMC = 1.0
# Mușchii + grăsimea nu pot fi aproape tot corpul (oase, organe, apă etc.).
PROCENT_MAXIM_MUSCHI_PLUS_GRASIME = 90.0


class Caracteristica(Enum):
    VARSTA = "Vârstă"
    MASA_CORPORALA = "Masă corporală"
    INALTIME = "Înălțime"
    INDICE_MASA_CORPORALA = "Indicele de masă corporală"
    PULS_MEDIU = "Pulsul mediu"
    PRESIUNE_SISTOLICA = "Presiunea arterială sistolică"
    PRESIUNE_DIASTOLICA = "Presiunea arterială diastolică"
    PROCENT_MASA_MUSCULARA = "Procent de masă musculară"
    PROCENT_GRASIME = "Procent de grăsime"
    NIVEL_STRES = "Niveluri de stres"
    GLICEMIE = "Glicemia din sânge"
    ORE_SOMN = "Orele petrecute dormind"


@dataclass(frozen=True)
class DefinitieCaracteristica:
    caracteristica: Caracteristica
    unitate: str
    minim: float
    maxim: float


@dataclass(frozen=True)
class Incoerenta:
    mesaj: str
    campuri: tuple[Caracteristica, ...]


DEFINITII: tuple[DefinitieCaracteristica, ...] = (
    DefinitieCaracteristica(Caracteristica.VARSTA, "ani", 18, 70),
    DefinitieCaracteristica(Caracteristica.MASA_CORPORALA, "kg", 40, 150),
    DefinitieCaracteristica(Caracteristica.INALTIME, "cm", 140, 210),
    DefinitieCaracteristica(Caracteristica.INDICE_MASA_CORPORALA, "kg/m²", 15, 40),
    DefinitieCaracteristica(Caracteristica.PULS_MEDIU, "bpm", 30, 200),
    DefinitieCaracteristica(Caracteristica.PRESIUNE_SISTOLICA, "mmHg", 70, 250),
    DefinitieCaracteristica(Caracteristica.PRESIUNE_DIASTOLICA, "mmHg", 40, 150),
    DefinitieCaracteristica(Caracteristica.PROCENT_MASA_MUSCULARA, "%", 20, 60),
    DefinitieCaracteristica(Caracteristica.PROCENT_GRASIME, "%", 3, 50),
    DefinitieCaracteristica(Caracteristica.NIVEL_STRES, "scală", 1, 10),
    DefinitieCaracteristica(Caracteristica.GLICEMIE, "mg/dL", 40, 300),
    DefinitieCaracteristica(Caracteristica.ORE_SOMN, "ore", 2, 12),
)


def formateaza_limite(definitie: DefinitieCaracteristica) -> str:
    return f"{definitie.minim:g} - {definitie.maxim:g} {definitie.unitate}"


def este_in_limite(definitie: DefinitieCaracteristica, valoare: float) -> bool:
    # NaN și infinit sunt respinse automat: comparațiile cu NaN sunt False.
    return definitie.minim <= valoare <= definitie.maxim


def citeste_valoare(definitie: DefinitieCaracteristica) -> float:
    """Cere o valoare numerică în limitele definite, până când este validă."""
    print(f"\nLimite: {formateaza_limite(definitie)}")
    mesaj = f"{definitie.caracteristica.value}: "
    while True:
        text = input(mesaj)
        try:
            valoare = float(text.strip().replace(",", "."))
        except ValueError:
            print("Introduceți un număr valid.")
            continue
        if not este_in_limite(definitie, valoare):
            print(f"Valoarea trebuie să fie între {formateaza_limite(definitie)}.")
            continue
        return valoare


def verifica_coerenta(valori: dict[Caracteristica, float]) -> list[Incoerenta]:
    """Verifică dacă valorile sunt compatibile între ele."""
    probleme: list[Incoerenta] = []
    sis = valori[Caracteristica.PRESIUNE_SISTOLICA]
    dia = valori[Caracteristica.PRESIUNE_DIASTOLICA]
    if sis <= dia:
        probleme.append(
            Incoerenta(
                "Presiunea sistolică trebuie să fie mai mare decât cea diastolică.",
                (Caracteristica.PRESIUNE_SISTOLICA, Caracteristica.PRESIUNE_DIASTOLICA),
            )
        )

    masa = valori[Caracteristica.MASA_CORPORALA]
    inaltime_m = valori[Caracteristica.INALTIME] / 100
    imc = valori[Caracteristica.INDICE_MASA_CORPORALA]
    imc_calculat = masa / inaltime_m**2
    if abs(imc - imc_calculat) > TOLERANTA_IMC:
        probleme.append(
            Incoerenta(
                f"IMC introdus ({imc:.1f}) nu corespunde masei și înălțimii "
                f"(calculat: {imc_calculat:.1f}).",
                (
                    Caracteristica.MASA_CORPORALA,
                    Caracteristica.INALTIME,
                    Caracteristica.INDICE_MASA_CORPORALA,
                ),
            )
        )

    muschi = valori[Caracteristica.PROCENT_MASA_MUSCULARA]
    grasime = valori[Caracteristica.PROCENT_GRASIME]
    if muschi + grasime > PROCENT_MAXIM_MUSCHI_PLUS_GRASIME:
        probleme.append(
            Incoerenta(
                f"Mușchi ({muschi:g}%) + grăsime ({grasime:g}%) depășesc "
                f"{PROCENT_MAXIM_MUSCHI_PLUS_GRASIME:g}% din corp.",
                (
                    Caracteristica.PROCENT_MASA_MUSCULARA,
                    Caracteristica.PROCENT_GRASIME,
                ),
            )
        )
    return probleme


def introduce_caracteristici() -> dict[Caracteristica, float]:
    """Cere toate caracteristicile, apoi reintroduce doar câmpurile incoerente."""
    valori = {
        definitie.caracteristica: citeste_valoare(definitie)
        for definitie in DEFINITII
    }
    while probleme := verifica_coerenta(valori):
        for problema in probleme:
            print(f"Eroare: {problema.mesaj}")
        de_reintrodus = {camp for p in probleme for camp in p.campuri}
        print("Reintroduceți valorile implicate:")
        for definitie in DEFINITII:
            if definitie.caracteristica in de_reintrodus:
                valori = {
                    **valori,
                    definitie.caracteristica: citeste_valoare(definitie),
                }
    return valori


def nume_coloana(caracteristica: Caracteristica) -> str:
    return caracteristica.name.lower()


def citeste_nume(eticheta: str) -> str:
    """Cere un nume (litere, spații, cratime) și îl normalizează."""
    while True:
        text = " ".join(input(f"{eticheta}: ").split())
        if not text:
            print("Numele nu poate fi gol.")
        elif len(text) > LUNGIME_MAXIMA_NUME:
            print(f"Maximum {LUNGIME_MAXIMA_NUME} de caractere.")
        elif not all(ch.isalpha() or ch in " -" for ch in text):
            print("Folosiți doar litere, spații și cratime.")
        else:
            return text.title()


def creeaza_tabel(conn: sqlite3.Connection) -> None:
    """Creează tabelul; limitele din DEFINITII sunt impuse și în baza de date."""
    coloane = ",\n    ".join(
        f"{nume_coloana(d.caracteristica)} REAL NOT NULL "
        f"CHECK ({nume_coloana(d.caracteristica)} "
        f"BETWEEN {d.minim:g} AND {d.maxim:g})"
        for d in DEFINITII
    )
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS astronauti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nume TEXT NOT NULL,
    prenume TEXT NOT NULL,
    {coloane},
    UNIQUE (nume, prenume)
)"""
        )


def exista_astronaut(conn: sqlite3.Connection, nume: str, prenume: str) -> bool:
    rand = conn.execute(
        "SELECT 1 FROM astronauti WHERE nume = ? AND prenume = ?", (nume, prenume)
    ).fetchone()
    return rand is not None


def salveaza_astronaut(
    conn: sqlite3.Connection,
    nume: str,
    prenume: str,
    valori: dict[Caracteristica, float],
) -> None:
    """Inserează astronautul sau îi actualizează valorile dacă există deja."""
    coloane = [nume_coloana(d.caracteristica) for d in DEFINITII]
    lista_coloane = ", ".join(["nume", "prenume", *coloane])
    semne = ", ".join("?" * (len(coloane) + 2))
    actualizari = ", ".join(f"{c} = excluded.{c}" for c in coloane)
    parametri = (nume, prenume, *(valori[d.caracteristica] for d in DEFINITII))
    with conn:
        conn.execute(
            f"INSERT INTO astronauti ({lista_coloane}) VALUES ({semne}) "
            f"ON CONFLICT(nume, prenume) DO UPDATE SET {actualizari}",
            parametri,
        )


def confirma(intrebare: str) -> bool:
    return input(f"{intrebare} (d/n): ").strip().lower() in ("d", "da")


def main() -> None:
    nume = citeste_nume("Nume de familie")
    prenume = citeste_nume("Prenume")
    with closing(sqlite3.connect(CALE_DB)) as conn:
        creeaza_tabel(conn)
        if exista_astronaut(conn, nume, prenume) and not confirma(
            "Astronautul există deja. Suprascrieți datele?"
        ):
            print("Nu s-a modificat nimic.")
            return
        valori = introduce_caracteristici()
        salveaza_astronaut(conn, nume, prenume, valori)
    print(f"\nDate salvate pentru {nume} {prenume} în {CALE_DB.name}:")
    for caracteristica, valoare in valori.items():
        print(f"  {caracteristica.value}: {valoare:g}")


if __name__ == "__main__":
    # Evită blocarea pe terminale care nu pot afișa diacritice (ex. cp1252).
    sys.stdout.reconfigure(errors="replace")
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nIntroducerea a fost anulată.")
        raise SystemExit(1)
    except sqlite3.Error as eroare:
        print(f"Eroare la baza de date: {eroare}")
        raise SystemExit(1)
