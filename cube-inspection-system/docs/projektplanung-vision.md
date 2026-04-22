# Technischer Ansatz: Bildverarbeitung und Qualitätsprüfung

## Überblick

Für die visuelle Qualitätsprüfung soll OpenCV eingesetzt werden. Die Aufnahmen erfolgen über die am Niryo Ned2 montierte Kamera an konfigurierbaren Positionen innerhalb der Robotersequenz. Vor jeder Aufnahme wartet das System kurz, damit der Arm zur Ruhe kommt. Pro Position wird ein Rohbild und ein annotiertes Ergebnisbild gespeichert.

## Beleuchtung

Die Erkennung basiert auf Farbfiltern im HSV-Farbraum. Gleichmäßiges, diffuses Licht ist daher wichtig, um harte Schatten und verfälschte Farbwerte zu vermeiden. Die HSV-Grenzen setzen eine hohe Sättigung voraus (S ≥ 150), wodurch Hintergrundobjekte wie der Holztisch zuverlässig ausgeschlossen werden.

## Farberkennung

Das Kamerabild wird von BGR nach HSV konvertiert. Mit definierten Grenzen für Farbton, Sättigung und Helligkeit entsteht eine Binärmaske, die nur die Würfeloberfläche enthält. Morphologische Operationen (Closing und Opening) bereinigen die Maske. Der Kernel wird bewusst klein gehalten (3×3 Pixel), damit die Augen-Löcher erhalten bleiben.

## Augenzahlerkennung

Die Augenzählung nutzt die Contour-Hierarchie von OpenCV (RETR_CCOMP). Dieser Modus liefert äußere Konturen und deren innere Löcher in einer zweistufigen Struktur.

**Würfelfläche finden:** Die größte äußere Kontur innerhalb plausibler Flächen- und Seitenverhältnis-Grenzen wird als Würfelseite identifiziert.

**Augen-Kandidaten filtern:** Die inneren Konturen dieser Fläche werden nach Größe und Kreisförmigkeit (Zirkularität) gefiltert.

**Ausreißer entfernen:** Ein medianbasierter Filter verwirft Konturen, deren Fläche deutlich unter dem Median liegt – das sind typischerweise Oberflächenritzen statt echte Augen.

Der Vorteil dieses Ansatzes: Es wird kein separater Grauwert-Threshold, keine Erosion und kein Convex Hull benötigt. OpenCV erkennt die Löcher in der Fläche direkt über die Hierarchie.
