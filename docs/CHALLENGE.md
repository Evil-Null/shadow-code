# PLAN.md კრიტიკული ანალიზი

> **Reviewer:** 5-Eye Team (Architect + Developer + LLM Engineer + QA + Tech Lead)
> **Verdict:** PLAN REQUIRES MAJOR REVISION
> **Critical Issues:** 7 | **High Issues:** 9 | **Medium Issues:** 6

---

## CRITICAL ISSUES (must fix before implementation)

### C1: Prompt ტექსტი არის PLACEHOLDER, არა რეალური

**პრობლემა:**
გეგმის ყველაზე მნიშვნელოვანი ნაწილი — სისტემური prompt — შეიცავს placeholder-ებს:
```
## bash
Executes a bash command and returns its output.
[ადაპტირებული BashTool/prompt.ts-დან]  ← ეს არის PLACEHOLDER
```

სისტემური prompt არის **მთელი პროექტის გული**. prompt-ის გარეშე ეს პროექტი უბრალოდ HTTP client + subprocess wrapper-ია. სწორედ prompt აქცევს shadow-gemma-ს "coding assistant"-ად.

**LLM Engineer:** Claude Code-ის prompt მუშაობს, რადგან Claude სპეციალურად არის ტრენირებული tool_use ფორმატზე. shadow-gemma-ს ასეთი ტრენინგი არ აქვს. prompt-ის ყოველი სიტყვა კრიტიკულია — შეცდომა prompt-ში = მოდელი ვერ იყენებს tools.

**რეკომენდაცია:** prompt.py-ს სრული, სიტყვა-სიტყვით ტექსტი უნდა იყოს გეგმაში.

---

### C2: Tool Call ფორმატი არ არის ტესტირებული მოდელზე

**პრობლემა:**
გეგმა ირჩევს `<tool_call>` ფორმატს თეორიული არგუმენტებით ("regex-ით ადვილი", "უნიკალური ტეგი"). მაგრამ:

1. shadow-gemma (Gemma 3) ტრენირებულია HTML/XML მონაცემებზე — `<tool_call>` შეიძლება მოდელმა HTML ტეგად აღიქვას
2. არ ვიცით მოდელი საიმედოდ გამოიტანს თუ არა JSON ამ ტეგებში
3. არ ვიცით მოდელი ერთ პასუხში რამდენჯერ შეძლებს ამ ფორმატის გამოყენებას
4. Gemma 3-ის chat template იყენებს `<start_of_turn>` ტეგებს — ეს ქმნის "ტეგების სივრცეს" სადაც `<tool_call>` დაიბნევა

**LLM Engineer:** 27B კვანტიზებული მოდელი (Q4_K_M) ხშირად "ივიწყებს" ფორმატის ინსტრუქციებს ხანგრძლივ საუბარში. ეს არის ცნობილი პრობლემა და მისი გადაწყვეტა მოითხოვს:
- ფორმატის ემპირიულ ტესტირებას სხვადასხვა სცენარში
- few-shot მაგალითებს prompt-ში
- fallback parsing სტრატეგიას

**QA Engineer:** რა ხდება თუ მოდელი დაწერს:
```
აი მაგალითი, როგორ უნდა გამოძახო tool:
<tool_call>
{"tool": "bash", "params": {"command": "ls"}}
</tool_call>
```
parser-ი ვერ განასხვავებს ახსნას გამოძახებისგან.

**რეკომენდაცია:** ფაზა 0 (ვალიდაცია) უნდა დაემატოს — 10+ ტესტი რეალურ მოდელთან, სხვადასხვა ფორმატის შედარება.

---

### C3: Streaming + Tool Call Parsing კონფლიქტი

**პრობლემა:**
გეგმის REPL loop:
```python
for chunk in ollama_client.chat_stream(...):
    print(chunk, end="", flush=True)  # ← ბეჭდავს რეალურ დროში
    full_response += chunk
# Parse tool calls AFTER full response
```

ეს ნიშნავს: მომხმარებელი ხედავს `<tool_call>{"tool": "bash"...}</tool_call>` ტექსტს ტერმინალში streaming-ის დროს. შემდეგ parser ამოიცნობს და ეშვება tool. მომხმარებლის გამოცდილება:

```
shadow> list files

ვნახოთ რა ფაილები გვაქვს.

<tool_call>
{"tool": "bash", "params": {"command": "ls -la"}}
</tool_call>                              ← მომხმარებელი ხედავს raw JSON-ს

[tool: bash] ls -la                       ← შემდეგ ხედავს შედეგს
total 48...
```

**Developer:** ეს ტექნიკურად მუშაობს, მაგრამ UX არის საშინელი. Claude Code არ აჩვენებს tool_use JSON-ს მომხმარებელს — აჩვენებს მხოლოდ "[Running: ls -la]".

**რეკომენდაცია:** Streaming buffer — `<tool_call>` დაწყებისას ტექსტი ბუფერში გადადის და არ იბეჭდება. თუ ვალიდური tool call-ია → tool ეშვება. თუ არა → ბუფერი იბეჭდება.

---

### C4: Token Estimation სრულიად არასანდოა

**პრობლემა:**
გეგმა:
```
ზუსტი: Ollama-ს prompt_eval_count + eval_count ბოლო response-იდან
სავარაუდო: len(text) / 4 (ინგლისური), len(text) / 2 (ქართული)
```

1. `len(text) / 4` არის GPT-2 tokenizer-ის ხეურისტიკა. Gemma 3 იყენებს SentencePiece tokenizer-ს, სადაც:
   - ინგლისური: ~1.3 tokens/word (~0.25 tokens/char) — მსგავსი
   - ქართული: **3-8 tokens/სიმბოლო** რადგან ქართული Unicode characters ხშირად byte-level fallback-ზეა
   - კოდი: ძალიან ვარიაბელური

2. `prompt_eval_count` მხოლოდ ბოლო response-ში ჩანს, არა cumulative
3. Truncation 100K-ზე, მაგრამ თუ estimation 2x-ით ცდება, context overflow მოხდება 50K-ზე

**Architect:** context overflow = Ollama error ან გაუარესებული პასუხები. ეს არის silent failure — მოდელი უბრალოდ დაიწყებს უაზრო პასუხების გენერაციას.

**რეკომენდაცია:**
- Ollama-ს `/api/embed` endpoint-ით ტოკენების ზუსტი დათვლა (ან tokenizer library)
- ან: conservative estimate `len(text) / 2` ყველასთვის (ქართულისთვისაც)
- ან: `prompt_eval_count`-ზე დაფუძნებული tracking (ყველაზე ზუსტი)

---

### C5: Tool Results "user" როლით — მოდელი დაიბნევა

**პრობლემა:**
```python
{"role": "user", "content": "<tool_result tool=\"bash\">...</tool_result>"}
```

მოდელი ხედავს "user"-ს ვინც წერს `<tool_result>`. ეს შეიძლება:
1. მოდელმა tool result აღიქვას როგორც მომხმარებლის ახალი მოთხოვნა
2. მოდელმა პასუხი გასცეს tool result-ს, არა ორიგინალ შეკითხვას
3. მრავალჯერადი tool call-ის შემდეგ, მოდელი "დაივიწყოს" ორიგინალი მოთხოვნა

**LLM Engineer:** ეს არის ცნობილი პრობლემა prompt-based tool calling-ში. გადაწყვეტა:
- tool result-ს წინ დაუმატო კონტექსტის მინიშნება
- ან: გამოიყენო Ollama-ს system message mid-conversation

**რეკომენდაცია:** Tool result ფორმატი უნდა იყოს:
```
[SYSTEM: Tool execution results below. Continue working on the user's original request.]

<tool_result tool="bash" success="true">
...output...
</tool_result>
```

---

### C6: არ არის Phase 0 (ემპირიული ვალიდაცია)

**პრობლემა:**
გეგმა პირდაპირ იწყება იმპლემენტაციით (ფაზა 1). არ არის ფაზა სადაც:
1. სხვადასხვა tool call ფორმატს ვტესტავთ მოდელზე
2. prompt-ის სიგრძის გავლენას ვამოწმებთ
3. ქართული + ინგლისური mixing-ის ქცევას ვაკვირდებით
4. few-shot vs zero-shot ეფექტურობას ვადარებთ
5. temperature-ს ოპტიმალურ მნიშვნელობას ვარჩევთ

**Tech Lead:** ფაზა 0 გარეშე, ფაზა 1-ში აღმოჩნდება, რომ არჩეული ფორმატი არ მუშაობს, და მთელი არქიტექტურა ხელახლა უნდა გადაკეთდეს.

**რეკომენდაცია:** ფაზა 0: ვალიდაცია (2-3 საათი) — curl/python ტესტებით დავადასტუროთ, რომ shadow-gemma საიმედოდ იყენებს არჩეულ ფორმატს.

---

### C7: bash tool-ში `shell=True` არის უსაფრთხოების ხვრელი

**პრობლემა:**
```python
subprocess.run(command, shell=True, ...)
```

`shell=True` ნიშნავს: `/bin/sh -c "command"`. ეს საშუალებას აძლევს:
- Shell injection: `ls; rm -rf /`
- Environment variable expansion: `echo $HOME`
- Pipe chains: `cat file | grep pattern`

**Security:** ეს ფუნქციონალურად საჭიროა (მომხმარებელს სჭირდება pipes, redirects). მაგრამ გეგმაში:
- არ არის მოხსენიებული, რომ `shell=True` არის შეგნებული არჩევანი
- არ არის interactive command detection (`vim`, `less`, `nano`)
- არ არის resource limit (`ulimit`)
- არ არის stdin blocking detection

**რეკომენდაცია:** არა აკრძალვა, არამედ:
- ცხადად დააფიქსირე რომ `shell=True` არის შეგნებული (სჭირდება pipes/redirects)
- Interactive command detection → error message
- Process group kill on timeout (`os.killpg`)
- stdin redirect to /dev/null

---

## HIGH ISSUES

### H1: Working Directory არ იცვლება bash-ის `cd` ბრძანებით

**პრობლემა:** `subprocess.run(cwd=self.working_directory)` — ყოველი command ახალ subprocess-ში ეშვება. `cd /tmp` მუშაობს ერთ command-ში, მაგრამ შემდეგი command კვლავ ძველ CWD-ში იქნება.

**Claude Code-ს აქვს:** persistent shell session რომელიც CWD-ს ინახავს calls-ს შორის.

**რეკომენდაცია:** `cd` command-ის detection + CWD update ლოგიკა.

### H2: Prompt-ის ზომა არ არის გაზომილი

4K tokens "შეფასება" შეიძლება რეალურად 8-12K იყოს (Claude Code-ის prompt ძალიან ვერბოსულია). ეს 128K-დან 10%-ს წაიღებს.

**რეკომენდაცია:** prompt ჩაწერე → გაზომე Ollama-ის `/api/embed` ან `tiktoken`-ით → ოპტიმიზირე.

### H3: არ არის Ctrl+C handling streaming-ის დროს

`KeyboardInterrupt` `requests.iter_lines()` შიგნით → unclosed connection, potential hang.

**რეკომენდაცია:** signal handler + abort mechanism.

### H4: glob tool `.git` ფილტრაცია pathlib-ით არაეფექტურია

`pathlib.Path.glob("**/*.py")` ჯერ ყველა ფაილს იპოვის (მათ შორის `.git/`-ში), შემდეგ ფილტრავ. დიდ რეპოში ეს ძალიან ნელია.

**რეკომენდაცია:** `os.walk` + manual filter ან `fnmatch`, რომელიც prune-ს `.git` dirs.

### H5: edit_file-ს არ ამოწმებს ფაილი წაკითხულია თუ არა

Claude Code-ში: FileEditTool არ მუშაობს თუ FileReadTool-ით ჯერ არ წაიკითხე. ეს prevent-ს აკეთებს blind edits-ს.

**რეკომენდაცია:** file read tracking state.

### H6: არ არის multiline input REPL-ში

`input("shadow> ")` მხოლოდ ერთ ხაზს კითხულობს. კოდის ჩასმა შეუძლებელია.

**რეკომენდაცია:** ფაზა 1-ში: `"""` delimiter ან `\` line continuation. ფაზა 3-ში: prompt_toolkit.

### H7: retry ლოგიკა არ არის tool call failure-ზე

თუ მოდელმა არასწორი JSON დაწერა, tool_result error-ით ბრუნდება. მაგრამ:
- რა ხდება თუ მოდელი კვლავ არასწორ JSON-ს იწერს? (infinite error loop)
- რა ხდება თუ მოდელი საერთოდ შეწყვეტს tool call-ების გამოყენებას?

**რეკომენდაცია:** consecutive error counter → 3 consecutive fail → warning to user.

### H8: grep fallback Python-ით არის ძალიან ნელი

დიდ რეპოში (10K+ ფაილი) Python `re` + `os.walk` = წუთები. ripgrep = წამები.

**რეკომენდაცია:** `grep -rn` (system grep) როგორც secondary fallback (ripgrep → system grep → Python).

### H9: few-shot მაგალითები არ არის prompt-ში

27B მოდელი ბევრად უკეთ ასრულებს ფორმატის ინსტრუქციებს few-shot მაგალითებით, ვიდრე მხოლოდ აღწერით.

**რეკომენდაცია:** 2-3 სრული მაგალითი (user → assistant with tool_call → tool_result → assistant final answer).

---

## MEDIUM ISSUES

### M1: `read_file` offset არის 0-based, Claude Code-ში 1-based
### M2: არ არის logging (debug mode)
### M3: არ არის config file (~/.shadow-code/config.json)
### M4: არ არის git integration ინსტრუქცია prompt-ში (commit/PR)
### M5: rich და prompt_toolkit არის optional, მაგრამ ფაზა 3 მათ ეფუძნება
### M6: არ არის model health check startup-ზე (Ollama running? Model loaded?)

---

## VERDICT

```
+------------------------------------------------------------------+
|                                                                    |
|   VERDICT: PLAN REQUIRES MAJOR REVISION                           |
|                                                                    |
|   The plan has a solid STRUCTURAL foundation but critically        |
|   lacks:                                                           |
|                                                                    |
|   1. Empirical validation phase (Phase 0)                         |
|   2. Actual prompt text (not placeholders)                        |
|   3. Streaming UX design (buffer for tool calls)                  |
|   4. Model-specific adaptations (27B Q4_K_M limitations)          |
|   5. Few-shot examples for reliable tool calling                  |
|   6. Accurate token measurement strategy                          |
|                                                                    |
|   The plan treats this as a "Python CLI project" when it's        |
|   actually an "LLM inference pipeline project" where the          |
|   prompt is the product and Python is just the wrapper.            |
|                                                                    |
+------------------------------------------------------------------+
```

---

**// END OF CHALLENGE.md**
