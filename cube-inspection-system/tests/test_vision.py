from pyniryo import NiryoRobot
import cv2
import numpy as np

# 1. Verbindung herstellen (IP anpassen, falls nötig)
robot_ip = "10.10.10.10" 
robot = NiryoRobot(robot_ip)

print("Starte Objekterkennung (Orange Würfel + Augenzahlen)...")
print("Drücke 'q' im Bildfenster, um das Programm zu beenden.")

try:
    while True:
        # Bild vom Roboter holen
        img_compressed = robot.get_img_compressed()
        img_array = np.frombuffer(img_compressed, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img is not None:
            # A) Bild in den HSV-Farbraum konvertieren
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # B) Farbbereich für ORANGE definieren
            # Diese Werte passen meist gut für helles Orange. 
            # Je nach Licht musst du sie evtl. leicht anpassen.
            lower_orange = np.array([5, 100, 100])
            upper_orange = np.array([25, 255, 255])
            
            # C) Maske für den Würfel erstellen
            mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
            
            # D) Konturen des Würfels finden
            contours, _ = cv2.findContours(mask_orange, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Nimm die größte orange Fläche
                largest_contour = max(contours, key=cv2.contourArea)
                
                # Prüfe, ob es auch wirklich groß genug für den Würfel ist
                if cv2.contourArea(largest_contour) > 1000:
                    
                    # Bounding Box (Rechteck) um den Würfel berechnen
                    x, y, w, h = cv2.boundingRect(largest_contour)
                    
                    # Grünes Rechteck um den Würfel zeichnen
                    cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    # --- JETZT DIE PUNKTE ZÄHLEN ---
                    
                    # Wir schneiden genau den Bereich des Würfels aus dem Bild aus (Region of Interest = ROI)
                    # Wir nehmen das Graustufenbild, weil uns für die Punkte nur Hell/Dunkel interessiert
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    roi_gray = gray[y:y+h, x:x+w]
                    
                    # Da die Punkte dunkler sind als der Würfel, filtern wir nach dunklen Stellen
                    # Alles was sehr dunkel ist, wird weiß, der Rest schwarz (THRESH_BINARY_INV)
                    # Der Wert '100' ist der Schwellenwert. Ggf. auf 80 oder 120 anpassen, falls Punkte fehlen.
                    _, thresh = cv2.threshold(roi_gray, 100, 255, cv2.THRESH_BINARY_INV)
                    
                    # Konturen der Punkte im Würfelbereich finden
                    dot_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    dot_count = 0
                    for dot in dot_contours:
                        area = cv2.contourArea(dot)
                        # Filter: Ein Punkt darf nicht zu winzig (Rauschen) und nicht riesig sein
                        if 10 < area < 300:
                            dot_count += 1
                            # Kleinen roten Kreis um den erkannten Punkt zeichnen (Koordinaten anpassen, da wir im ROI sind!)
                            dx, dy, dw, dh = cv2.boundingRect(dot)
                            cv2.rectangle(img, (x+dx, y+dy), (x+dx+dw, y+dy+dh), (0, 0, 255), 1)
                    
                    # Ergebnis über den Würfel schreiben
                    text = f"Wuerfel! Augen: {dot_count}"
                    cv2.putText(img, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Bilder anzeigen
            cv2.imshow("Logitech Wuerfel Erkennung", img)
            
            # Hilfreich zum Debuggen: Zeigt an, was OpenCV für "dunkle Punkte" hält
            # cv2.imshow("Punkte-Filter (Thresh)", thresh) 
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Beende Stream...")
                break
        else:
            print("Fehler: Bild konnte nicht dekodiert werden.")
            break

except Exception as e:
    print(f"Fehler: {e}")

finally:
    cv2.destroyAllWindows()
    robot.close_connection()