import os
import sqlite3
import shutil

for db in ("media_pipeline.db", "media.db"):
    con = sqlite3.connect(db)
    cur = con.cursor()
    try:
        cur.execute("delete from analysis_results")
        cur.execute("delete from images")
        con.commit()
        print(db, "cleared")
    except sqlite3.OperationalError as e:
        print(db, "skip:", e)
    con.close()

upload_dir = "uploads"
total = 0
for root, dirs, files in os.walk(os.path.join(upload_dir, "2026")):
    for f in files:
        p = os.path.join(root, f)
        os.remove(p)
        total += 1
        print("removed", p)
print("files removed:", total)

for f in ("red_car.jpg", "test_arial.jpg"):
    if os.path.exists(f):
        os.remove(f)
        print("removed", f)

for d in ("uploads/2026/08", "uploads/2026"):
    if os.path.isdir(d) and not os.listdir(d):
        os.rmdir(d)
        print("removed empty dir", d)