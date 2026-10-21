import json, time
import feedparser
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()          # reads GEMINI_API_KEY from .env
MODEL = "gemini-2.5-flash"
RESUME = open("resume.txt", encoding="utf-8").read()
FEEDS = ["https://weworkremotely.com/remote-jobs.rss"]
MIN_SCORE = 70                   # only keep jobs scoring this or higher
MAX_JOBS = 15                    # per run, keeps you inside free limits
PAUSE = 7                        # seconds between calls (free-tier limit)


def load_seen():
       try:
           return set(json.load(open("seen.json")))
       except FileNotFoundError:
           return set()


def ask(prompt, as_json=False):
       cfg = types.GenerateContentConfig(
           response_mime_type="application/json" if as_json else "text/plain"
       )
       r = client.models.generate_content(model=MODEL, contents=prompt, config=cfg)
       time.sleep(PAUSE)
       return r.text


def score_job(title, desc):
       prompt = f"""Compare this resume to the job posting.
   Reply ONLY with JSON in this format:
   {{"score": <number 0-100>, "reasons": ["..."], "missing_skills": ["..."]}}

   RESUME:
   {RESUME}

   JOB TITLE: {title}
   JOB DESCRIPTION:
   {desc}"""
       return json.loads(ask(prompt, as_json=True))


def draft_opener(title, desc):
       prompt = f"""Write a 3-sentence cover letter opener for the job '{title}',
   based on this resume. Be specific and natural, no clichés.

   RESUME:
   {RESUME}

   JOB DESCRIPTION:
   {desc}"""
       return ask(prompt).strip()


def main():
       seen, results, count = load_seen(), [], 0
       for url in FEEDS:
           for e in feedparser.parse(url).entries:
               if e.link in seen:
                   continue
               if count >= MAX_JOBS:
                   break
               count += 1
               desc = getattr(e, "summary", "")
               try:
                   s = score_job(e.title, desc)
                   if float(s.get("score", 0)) >= MIN_SCORE:
                       s["opener"] = draft_opener(e.title, desc)
                       results.append({"title": e.title, "link": e.link, **s})
                   seen.add(e.link)
               except Exception as err:
                   print(f"Skipped '{e.title}': {err}")

       json.dump(sorted(seen), open("seen.json", "w"))
       results.sort(key=lambda x: -float(x["score"]))

       with open("results.md", "w", encoding="utf-8") as f:
           f.write("# Daily job matches\n\n")
           for r in results:
               f.write(f"## {r['title']} (score {r['score']})\n{r['link']}\n\n")
               f.write("Why it fits: " + "; ".join(r.get("reasons", [])) + "\n\n")
               f.write("Missing: " + ", ".join(r.get("missing_skills", [])) + "\n\n")
               f.write(f"Opener: {r['opener']}\n\n---\n\n")

       print(f"Scanned {count} jobs, {len(results)} matches. See results.md")


if __name__ == "__main__":
       main()