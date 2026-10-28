import sys
sys.stdout.reconfigure(encoding="utf-8")
import ali_post, tracker
tracker.save = lambda data: None  # dry run: nothing is saved or sent
for n in range(3):
    p = ali_post.make_post()
    print(f"===== SAMPLE {n+1} ({p and p['label']})")
    if p:
        print(p["text"]); print("IMAGE", p["image"]); print("LINK", p["link"][:60])
