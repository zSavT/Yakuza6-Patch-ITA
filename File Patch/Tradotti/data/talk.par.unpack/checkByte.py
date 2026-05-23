import os
import re
import codecs
import argparse
import sys

def unescape_po_string(s):
    """
    Decodifica i caratteri di escape (es. \n diventa un vero a capo, \" diventa ").
    Questo è fondamentale perché nel gioco \n occupa 1 byte, non 2.
    """
    try:
        return codecs.decode(s, 'unicode_escape')
    except Exception:
        return s

def check_po_file(filepath):
    """Analizza un singolo file .po e restituisce una lista di errori, se presenti."""
    errors = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_max_bytes = None
    current_ctxt = None
    current_msgstr = ""
    in_msgstr = False
    block_start_line = 0

    def evaluate_block():
        # Funzione interna per valutare il blocco appena terminato di leggere
        nonlocal current_max_bytes, current_ctxt, current_msgstr, block_start_line
        
        if current_max_bytes is not None:
            unescaped_str = unescape_po_string(current_msgstr)
            # Codifichiamo in UTF-8 per contare i byte reali (le accentate valgono 2)
            actual_bytes = len(unescaped_str.encode('utf-8'))

            if actual_bytes > current_max_bytes:
                # Tronchiamo il testo per la stampa a schermo se è troppo lungo
                preview_text = unescaped_str.replace('\n', ' ')
                if len(preview_text) > 40:
                    preview_text = preview_text[:40] + "..."

                errors.append({
                    'line': block_start_line,
                    'ctxt': current_ctxt or "Sconosciuto",
                    'actual': actual_bytes,
                    'max': current_max_bytes,
                    'text': preview_text
                })

    for i, line in enumerate(lines):
        line = line.strip()
        line_num = i + 1

        # Cerca il commento con il limite di byte
        max_bytes_match = re.match(r'#\.\s*Max bytes:\s*(\d+)', line)
        if max_bytes_match:
            if in_msgstr:
                evaluate_block()
            
            current_max_bytes = int(max_bytes_match.group(1))
            current_ctxt = None
            current_msgstr = ""
            in_msgstr = False
            block_start_line = line_num
            continue

        # Cerca l'ID di contesto
        if line.startswith('msgctxt'):
            ctxt_match = re.search(r'msgctxt\s+"(.*)"', line)
            if ctxt_match:
                current_ctxt = ctxt_match.group(1)
            continue

        # Intercetta l'inizio della traduzione
        if line.startswith('msgstr'):
            in_msgstr = True
            str_match = re.search(r'msgstr\s+"(.*)"', line)
            if str_match:
                current_msgstr += str_match.group(1)
            continue

        # Gestisce le stringhe multi-riga della traduzione
        if in_msgstr:
            if line.startswith('"') and line.endswith('"'):
                current_msgstr += line[1:-1]
            elif line != "" and not line.startswith('"'):
                # Se la riga non inizia con le virgolette ed è piena, il blocco msgstr è finito
                evaluate_block()
                in_msgstr = False
                current_max_bytes = None

    # Valuta l'ultimo blocco se il file finisce senza righe vuote
    if in_msgstr:
        evaluate_block()

    return errors

def main():
    parser = argparse.ArgumentParser(description="Verifica i limiti di byte nei file .po")
    parser.add_argument("directory", nargs="?", default=".", help="Cartella madre da cui partire (default: cartella corrente)")
    args = parser.parse_args()

    root_dir = args.directory
    if not os.path.isdir(root_dir):
        print(f"Errore: La cartella '{root_dir}' non esiste.")
        sys.exit(1)

    print(f"Avvio scansione nella cartella: {os.path.abspath(root_dir)}")
    print("-" * 60)

    total_files = 0
    files_with_errors = 0
    total_errors = 0

    # Scansione ricorsiva delle cartelle
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.po'):
                total_files += 1
                filepath = os.path.join(dirpath, filename)
                
                errors = check_po_file(filepath)
                if errors:
                    files_with_errors += 1
                    total_errors += len(errors)
                    print(f"\n[!] Trovati errori nel file: {filepath}")
                    for err in errors:
                        print(f"    - Riga {err['line']} | Offset: {err['ctxt']}")
                        print(f"      Byte usati: {err['actual']} / {err['max']} (SFORA DI {err['actual'] - err['max']} BYTE)")
                        print(f"      Testo: \"{err['text']}\"")

    print("-" * 60)
    if total_errors == 0:
        print(f"OTTIMO! Controllati {total_files} file .po. Nessuno sforo rilevato.")
    else:
        print(f"ATTENZIONE: Trovati {total_errors} sforamenti distribuiti in {files_with_errors} file (su {total_files} file totali).")
        sys.exit(1)

if __name__ == "__main__":
    main()