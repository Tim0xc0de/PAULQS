# Wie erkennt unser System einen Würfel?

Eine einfache Erklärung, wie die Bildverarbeitung funktioniert – Schritt für Schritt.

---

## Inhaltsverzeichnis

1. [Das große Bild](#1-das-große-bild)
2. [Schritt 1: Farbe erkennen](#2-schritt-1-farbe-erkennen)
3. [Schritt 2: Augenzahl zählen](#3-schritt-2-augenzahl-zählen)
4. [Wie haben wir getestet?](#4-wie-haben-wir-getestet)
5. [Wie wurde es immer besser?](#5-wie-wurde-es-immer-besser)

---

## 1. Das große Bild

Stell dir vor, du hältst einen bunten Würfel vor eine Kamera.
Das System muss zwei Fragen beantworten:

> **Frage 1:** „Welche Farbe hat der Würfel?"
> **Frage 2:** „Wie viele Augen zeigt er?"

Das klingt einfach – für uns Menschen geht das in einer Sekunde.
Aber ein Computer sieht kein „Blau" und kein „Auge".
Er sieht nur **Millionen von Zahlen** (Pixel).

Unser System macht das in **drei großen Schritten**:

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│             │     │                 │     │                  │
│  Kamerabild │────>│  Farbe finden   │────>│  Augen zählen    │
│  aufnehmen  │     │  (Farbmaske)    │     │  (Löcher zählen) │
│             │     │                 │     │                  │
└─────────────┘     └─────────────────┘     └──────────────────┘
                            │                        │
                            v                        v
                    ┌───────────────┐        ┌───────────────┐
                    │ Farbe: "blau" │        │ Augen: 4      │
                    └───────────────┘        └───────────────┘
```

---

## 2. Schritt 1: Farbe erkennen

### 2.1 Was sieht der Computer?

Ein Bild besteht aus winzigen Punkten – den **Pixeln**.
Jeder Pixel hat drei Werte: **Rot**, **Grün** und **Blau** (RGB).

```
Beispiel: Ein einzelner Pixel

  Rot  = 30
  Grün = 80
  Blau = 200    → Das ergibt für uns: "Blau"
```

Aber: Der Computer weiß nicht, was „Blau" ist.
Für ihn ist das nur `(30, 80, 200)`.

### 2.2 Der Trick: HSV statt RGB

RGB ist unpraktisch zum Filtern. Deshalb wandeln wir das Bild
in ein anderes Farbsystem um: **HSV**.

```
HSV = Hue (Farbton) + Saturation (Sättigung) + Value (Helligkeit)

  ┌─────────────────────────────────────────────────────┐
  │                    Farbton (Hue)                     │
  │                                                     │
  │  0°    30°    60°   90°   120°  150°   180°         │
  │  Rot   Orange Gelb  Grün  Blau  Lila   Rot          │
  │  ├──────┼──────┼──────┼──────┼──────┼──────┤         │
  │                                                     │
  │  Stell dir einen Regenbogen als Zahlenstrahl vor!    │
  └─────────────────────────────────────────────────────┘
```

Der Vorteil: Die **Farbe** steckt jetzt in einer einzigen Zahl (dem Hue).
Egal ob hell, dunkel, im Schatten – der Hue bleibt ungefähr gleich.

### 2.3 Farbfilter: „Zeig mir nur das Blaue!"

Wir definieren für jede Farbe einen **erlaubten Bereich**:

```
Unsere Farb-Tabelle (vereinfacht):

  Farbe     │  Hue-Bereich  │  Beispiel
  ──────────┼───────────────┼──────────────────
  Orange    │    5 – 25     │  🟧 Klassischer Spielwürfel
  Rot       │  0–10, 160–180│  🟥 (Rot liegt am Rand, braucht 2 Bereiche!)
  Gelb      │   20 – 35     │  🟨
  Grün      │   35 – 85     │  🟩
  Blau      │  100 – 130    │  🟦
  Lila      │  125 – 155    │  🟪
```

Für jeden Pixel im Bild fragt das System:
> „Liegt dein Hue-Wert im erlaubten Bereich?"

- **Ja** → Pixel wird **weiß** (gehört zum Würfel)
- **Nein** → Pixel wird **schwarz** (gehört nicht dazu)

Das Ergebnis ist eine **Farbmaske** – ein Schwarz-Weiß-Bild:

```
  Originalbild:                    Farbmaske (Blau-Filter):

  ┌──────────────────┐             ┌──────────────────┐
  │                  │             │                  │
  │    ┌────────┐    │             │    ┌────────┐    │
  │    │ ● ● ● │    │             │    │▓▓▓▓▓▓▓▓│    │
  │    │ ● ● ● │    │    ────>    │    │▓▓▓▓▓▓▓▓│    │
  │    └────────┘    │             │    └────────┘    │
  │                  │             │                  │
  └──────────────────┘             └──────────────────┘
  (Buntes Foto)                    (Nur der blaue Würfel ist weiß)
```

### 2.4 Auto-Erkennung: Alle Farben durchprobieren

Woher weiß das System, welche Farbe der Würfel hat?
Es probiert einfach **alle Farben** nacheinander durch!

```
  Versuch 1: Orange-Filter  → Ergebnis: kein Würfel gefunden     ✗
  Versuch 2: Rot-Filter     → Ergebnis: kein Würfel gefunden     ✗
  Versuch 3: Gelb-Filter    → Ergebnis: kein Würfel gefunden     ✗
  Versuch 4: Grün-Filter    → Ergebnis: kein Würfel gefunden     ✗
  Versuch 5: Blau-Filter    → Ergebnis: großer Würfel gefunden!  ✓  ← Gewinner!
  Versuch 6: Lila-Filter    → Ergebnis: kein Würfel gefunden     ✗
```

Die Farbe, bei der der **größte Würfel** gefunden wird, gewinnt.
So funktioniert der `color="auto"`-Modus.

### 2.5 Aufräumen: Morphologie

Die Farbmaske ist noch nicht perfekt. Es gibt kleine Störungen:

```
  Rohe Farbmaske:                 Nach dem Aufräumen:

  ┌──────────────────┐             ┌──────────────────┐
  │  .               │             │                  │
  │    ┌──.─────┐    │             │    ┌────────┐    │
  │    │▓▓ ▓▓▓▓▓│    │             │    │▓▓▓▓▓▓▓▓│    │
  │    │▓▓▓▓.▓▓▓│    │    ────>    │    │▓▓▓▓▓▓▓▓│    │
  │    └────────┘ .  │             │    └────────┘    │
  │       .          │             │                  │
  └──────────────────┘             └──────────────────┘
  (Kleine Löcher + Pixel-Müll)     (Sauber!)
```

Dafür benutzen wir **Morphologie-Operationen** – das sind wie kleine Stempel:

- **Closing** (Schließen): Füllt winzige Löcher in der Maske
  → Stell dir vor, du streichst mit einem kleinen Pinsel über Kratzer
- **Opening** (Öffnen): Entfernt winzige Pixel-Krümel außerhalb
  → Stell dir vor, du pustest Staub vom Bild

---

## 3. Schritt 2: Augenzahl zählen

### 3.1 Die Idee: Löcher zählen

Jetzt kommt der clevere Teil. Schau dir die Farbmaske nochmal an:

```
  Farbmaske eines Würfels mit 4 Augen:

  ┌────────────────┐
  │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│
  │▓▓▓ ○ ▓▓▓▓ ○ ▓▓▓│     ○ = Loch (Auge = nicht-farbiger Bereich)
  │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│     ▓ = Würfelfläche (farbig)
  │▓▓▓ ○ ▓▓▓▓ ○ ▓▓▓│
  │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│
  └────────────────┘
```

Die Augen sind **Löcher** in der Farbfläche!
Warum? Weil die Augen (Punkte) eine **andere Farbe** haben als der Würfel.
Zum Beispiel: Blauer Würfel, weiße Augen → Blau-Filter sieht die Augen nicht.

> **Augen zählen = Löcher in der Farbmaske zählen**

### 3.2 Konturen und Hierarchie

OpenCV (unsere Bildverarbeitungs-Bibliothek) kann **Konturen** finden.
Eine Kontur ist der Umriss eines zusammenhängenden Bereichs.

```
  Kontur-Hierarchie (RETR_CCOMP):

  ┌─── Äußere Kontur (Parent) = Würfelfläche ───┐
  │                                               │
  │    ┌── Innere Kontur 1 ──┐                    │
  │    │       (Loch = Auge) │                    │
  │    └─────────────────────┘                    │
  │                                               │
  │    ┌── Innere Kontur 2 ──┐                    │
  │    │       (Loch = Auge) │                    │
  │    └─────────────────────┘                    │
  │                                               │
  │    ┌── Innere Kontur 3 ──┐                    │
  │    │       (Loch = Auge) │                    │
  │    └─────────────────────┘                    │
  │                                               │
  └───────────────────────────────────────────────┘

  Parent hat 3 Kinder → 3 Augen!
```

So funktioniert es:
1. **Finde die größte äußere Kontur** → Das ist der Würfel
2. **Zähle die Kinder (innere Konturen)** → Das sind die Augen

### 3.3 Filter: Nicht jedes Loch ist ein Auge

Es gibt auch falsche Löcher (z.B. kleine Kratzer oder Reflexionen).
Deshalb prüfen wir jedes Loch mit **drei Filtern**:

```
  Filter 1: FLÄCHE
  ─────────────────
  Ist das Loch groß genug?  (mindestens 30 Pixel²)
  Ist das Loch klein genug? (höchstens 800 Pixel²)

  ✓ Echtes Auge: ~100-400 Pixel²
  ✗ Winziger Kratzer: 5 Pixel²      → zu klein, ignorieren
  ✗ Riesiges Loch: 2000 Pixel²      → zu groß, ignorieren


  Filter 2: RUNDHEIT (Circularity)
  ──────────────────────────────────
  Ist das Loch rund?

  Circularity = 4π × Fläche / Umfang²

  Perfekter Kreis: Circularity = 1.0
  Unser Minimum:   Circularity > 0.45

  ✓ Rundes Auge:    Circularity ≈ 0.8    → zählen!
  ✗ Länglicher Riss: Circularity ≈ 0.2   → ignorieren


  Filter 3: AUSREISSER-ENTFERNUNG
  ────────────────────────────────
  Sind alle Löcher ähnlich groß?

  Echte Augen auf einem Würfel sind ungefähr gleich groß.
  Wenn ein Loch viel kleiner ist als die anderen → Ausreißer!

  Beispiel:  Flächen = [120, 130, 125, 15, 128]
             Median  = 125
             Schwelle = 125 × 0.4 = 50
             → 15 ist kleiner als 50 → wird nicht gezählt!
  Ergebnis: 4 Augen (statt 5)
```

### 3.4 Fallback: Wenn Löcher nicht funktionieren

Manchmal hat der Würfel **keine farbigen Löcher** – zum Beispiel wenn
die Augen nur leicht eingeprägt sind (gleiche Farbe, nur eine Vertiefung).

Dann greift der **Fallback-Modus**: Statt nach Löchern in der Farbmaske
sucht das System nach **dunklen Stellen** im Graustufenbild.

```
  Normaler Modus:                  Fallback-Modus:
  (Farbmaske → Löcher zählen)      (Graustufenbild → dunkle Stellen)

  ┌──────────┐                     ┌──────────┐
  │▓▓ ○ ▓▓ ○ │                     │░░ ■ ░░ ■ │
  │▓▓▓▓▓▓▓▓▓▓│     Klappt nicht?   │░░░░░░░░░░│     ■ = dunkel
  │▓▓ ○ ▓▓ ○ │     ────────────>   │░░ ■ ░░ ■ │     ░ = hell
  └──────────┘                     └──────────┘

  Löcher = 4                        Dunkle Stellen = 4
```

---

## 4. Wie haben wir getestet?

### 4.1 Das Test-Setup

Wir haben ein eigenes **Test-Programm** gebaut (`test_vision_usb.py`),
das eine USB-Webcam benutzt – ganz ohne Roboter.

```
  ┌─────────────────────────────────────────┐
  │                                         │
  │    USB-Kamera (Logitech Webcam)         │
  │           │                             │
  │           ▼                             │
  │    ┌─────────────┐                      │
  │    │  Livebild   │  ← Echtzeit-Vorschau│
  │    │             │                      │
  │    │  [Würfel]   │                      │
  │    │             │                      │
  │    ├─────────────┤                      │
  │    │ Analysieren │ Beenden │            │
  │    └─────────────┘                      │
  │                                         │
  │    Per Klick auf "Analysieren":         │
  │    → Bild einfrieren                    │
  │    → Erkennung durchführen              │
  │    → Ergebnis anzeigen                  │
  │                                         │
  └─────────────────────────────────────────┘
```

### 4.2 Das Ergebnis-Fenster (Composite)

Nach der Analyse zeigt das System ein **Gesamtbild**:

```
  ┌───────────────────────────────────────────────┐
  │  ERGEBNIS: 4 Augen erkannt                    │  ← Grün = OK (1-6)
  ├───────────────────────────────────────────────┤
  │ ■ Farbe: blau                                 │  ← Erkannte Farbe + Farbfeld
  ├───────────────┬───────────────┬───────────────┤
  │               │               │               │
  │   Ergebnis    │    Maske      │     ROI       │
  │  (mit Box)    │ (Schwarz/Weiß)│  (Ausschnitt) │
  │               │               │               │
  ├───────────────┴───────────────┴───────────────┤
  │   Ergebnis        Maske            ROI        │  ← Beschriftungen
  └───────────────────────────────────────────────┘
```

Dieses Composite-Bild wird auch **gespeichert**, damit man es sich
später nochmal anschauen kann.

### 4.3 Gespeicherte Bilder

Bei jeder Analyse werden **sechs Bilder** gespeichert:

```
  vision_captures/
  └── run_1_20260422_131749/
      ├── 01_raw.jpg          ← Rohbild (direkt von der Kamera)
      ├── 02_result.jpg       ← Ergebnis (mit grüner Box + Augenzahl)
      ├── 03_mask.jpg         ← Farbmaske (Schwarz-Weiß)
      ├── 04_dark_spots.jpg   ← Dunkle-Stellen-Maske (nur bei Fallback)
      ├── 05_roi.jpg          ← ROI-Ausschnitt (nur der Würfel)
      └── 06_composite.jpg    ← Gesamtbild (alles zusammen)
```

So konnten wir bei jedem Testlauf genau nachvollziehen,
**was das System gesehen hat** und **warum** es sich so entschieden hat.

---

## 5. Wie wurde es immer besser?

Die Erkennung war nicht sofort perfekt. Wir haben sie in mehreren
Runden verbessert – jede Runde hat ein Problem gelöst.

### Übersicht der Verbesserungsrunden

```
  Runde │ Problem                        │ Lösung
  ──────┼────────────────────────────────┼─────────────────────────────────
    1   │ Nur orange Würfel erkennbar    │ Farb-Tabelle mit 6 Farben
    2   │ Farbe muss manuell angegeben   │ Auto-Modus (alle Farben testen)
    3   │ Keine Farbanzeige im Ergebnis  │ Farberkennung + Composite erweitert
    4   │ Augenzahl manchmal zu hoch     │ Circularity-Filter + Ausreißer
    5   │ Fallback bei geprägten Würfeln │ Dunkle-Stellen-Erkennung
```

### Runde 1: Nur orange?

**Problem:**
Am Anfang konnte das System nur **orange Würfel** erkennen.
Der Farbfilter war fest auf Orange eingestellt.

**Lösung:**
Wir haben eine **Farb-Tabelle** mit sechs Farben erstellt:

```
  VORHER:                           NACHHER:

  Orange: Hue 5–25  ← Nur das!     Orange: Hue 5–25
                                    Rot:    Hue 0–10 + 160–180
                                    Gelb:   Hue 20–35
                                    Grün:   Hue 35–85
                                    Blau:   Hue 100–130
                                    Lila:   Hue 125–155
```

### Runde 2: Welche Farbe hat der Würfel?

**Problem:**
Man musste dem System vorher **sagen**, welche Farbe der Würfel hat.
Wenn man „orange" sagte und der Würfel blau war → nichts erkannt.

**Lösung:**
Der **Auto-Modus**. Das System probiert alle 6 Farben durch:

```
  ┌────────┐    ┌──────────────┐    ┌──────────────┐
  │  Bild  │───>│ Orange-Test  │───>│ Gefunden?    │── Nein ──┐
  └────────┘    └──────────────┘    └──────────────┘          │
       │                                                      │
       │        ┌──────────────┐    ┌──────────────┐          │
       └───────>│  Rot-Test    │───>│ Gefunden?    │── Nein ──┤
                └──────────────┘    └──────────────┘          │
                                                              │
                        ... (Gelb, Grün) ...                  │
                                                              │
                ┌──────────────┐    ┌──────────────┐          │
                │  Blau-Test   │───>│ Gefunden?    │── JA! ───┤
                └──────────────┘    └──────────────┘          │
                                                              │
                                                              ▼
                                                    ┌──────────────┐
                                                    │ Größter Fund │
                                                    │    gewinnt   │
                                                    └──────────────┘
```

### Runde 3: Welche Farbe wurde erkannt?

**Problem:**
Das System zeigte zwar die Augenzahl an, aber **nicht die Farbe**.
Man konnte nicht sehen, ob die Farberkennung richtig lag.

**Lösung:**
Im Ergebnis-Composite wird jetzt eine **zweite Info-Zeile** angezeigt
mit dem Farbnamen und einem kleinen farbigen Quadrat:

```
  ┌──────────────────────────────────────┐
  │  ERGEBNIS: 4 Augen erkannt          │
  ├──────────────────────────────────────┤
  │  ■ Farbe: blau                       │  ← NEU!
  ├──────────────────────────────────────┤
  │  ...                                 │
```

Die Farbe wird erkannt, indem der **Median-Hue** aller farbigen Pixel
im Würfel-Bereich berechnet und mit der Farb-Tabelle abgeglichen wird.

### Runde 4: Zu viele Augen?

**Problem:**
Manchmal wurde eine zu hohe Augenzahl erkannt.
Kleine Kratzer, Reflexionen oder Schatten wurden als Augen gezählt.

**Lösung:**
Drei Filter nacheinander:

```
  Schritt 1: Flächen-Filter
  ┌─────────────────────────────────────┐
  │  Alle Löcher sammeln                │
  │                                     │
  │  Loch A: 150 px²  ← OK             │
  │  Loch B: 140 px²  ← OK             │
  │  Loch C:   8 px²  ← Zu klein! Weg  │
  │  Loch D: 155 px²  ← OK             │
  │  Loch E: 145 px²  ← OK             │
  └─────────────────────────────────────┘

  Schritt 2: Rundheits-Filter
  ┌─────────────────────────────────────┐
  │  Loch A: Circ = 0.82  ← Rund! OK   │
  │  Loch B: Circ = 0.79  ← Rund! OK   │
  │  Loch D: Circ = 0.25  ← Länglich!  │  → Kratzer, weg damit
  │  Loch E: Circ = 0.85  ← Rund! OK   │
  └─────────────────────────────────────┘

  Schritt 3: Ausreißer-Filter
  ┌─────────────────────────────────────┐
  │  Flächen: [150, 140, 145]           │
  │  Median:   145                      │
  │  Alle > 145 × 0.4 = 58?  → Ja!     │
  │  Ergebnis: 3 Augen                  │
  └─────────────────────────────────────┘
```

### Runde 5: Geprägte Würfel (Fallback)

**Problem:**
Manche Würfel haben Augen, die **die gleiche Farbe** wie der Würfel haben –
nur leicht eingedrückt (geprägt). Die Löcher-Methode findet dann **0 Augen**.

**Lösung:**
Ein Fallback, der das Graustufenbild analysiert:

```
  Normaler Weg funktioniert nicht?
  (0 Löcher in der Farbmaske)
          │
          ▼
  ┌─────────────────────────────────┐
  │  Fallback: Dunkle Stellen      │
  │                                 │
  │  1. Würfel-ROI in Graustufen   │
  │  2. Adaptiver Threshold:       │
  │     "Wo ist es lokal dunkler?" │
  │  3. Dunkle Bereiche = Augen    │
  └─────────────────────────────────┘

  Adaptiver Threshold erklärt:

  ┌──────────────────────────────┐
  │  Für jeden Pixel:            │
  │                              │
  │  Durchschnitt der Umgebung   │
  │  (31×31 Pixel Nachbarschaft) │
  │          │                   │
  │          ▼                   │
  │  Pixel deutlich dunkler?     │
  │    Ja  → Markieren (= Auge) │
  │    Nein → Ignorieren         │
  └──────────────────────────────┘
```

---

## Zusammenfassung

```
  ┌────────────────────────────────────────────────────────────┐
  │                                                            │
  │   1. Bild aufnehmen (Kamera)                               │
  │                    │                                        │
  │                    ▼                                        │
  │   2. Farbmaske erstellen (HSV-Filter + Morphologie)        │
  │      → Für jede Farbe einzeln testen (Auto-Modus)          │
  │                    │                                        │
  │                    ▼                                        │
  │   3. Würfel finden (größte äußere Kontur)                  │
  │                    │                                        │
  │                    ▼                                        │
  │   4. Farbe bestimmen (Median-Hue im Würfel-ROI)           │
  │                    │                                        │
  │                    ▼                                        │
  │   5. Augen zählen (innere Konturen = Löcher)              │
  │      → Filter: Fläche, Rundheit, Ausreißer                │
  │      → Fallback: Dunkle Stellen bei 0 Löchern             │
  │                    │                                        │
  │                    ▼                                        │
  │   6. Ergebnis: "4 Augen, Farbe: blau"                     │
  │                                                            │
  └────────────────────────────────────────────────────────────┘
```

### Dateien im Projekt

| Datei | Was sie macht |
|---|---|
| `detection.py` | Würfel finden + Augen zählen + Farbe erkennen |
| `image_processing.py` | Farb-Tabelle (HSV-Bereiche) + Morphologie + Dunkle-Stellen |
| `test_vision_usb.py` | Test-Programm mit USB-Kamera und GUI |
