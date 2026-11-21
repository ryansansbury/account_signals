# Decisions

What was decided and why. Every rule or number changed after the real data was seen. The owner's decisions come first and the build's follow.

## The owner's decisions, November 9

The page uses real company names with a private exclusion list applied before anything is read (D1). The ideal customer is a company building out revenue operations (D2). News stays out of the core build (D3). The briefs come from Claude Sonnet 5.5, Claude Haiku 5.5, and GPT-6 Luna (D4). The page launches on its own (D5). A tool maker on the exclusion list may appear as a quoted tool and never as an account (D6). A few more companies stay out by hand and the read companies' names get a skim before any model sees them (D7). The first touch is written for a generic seller with placeholders for both names and nothing in it reads as the author pitching a real company (D8). Size is the count of open roles and never a headcount (D9).

## The owner's decisions, November 10

No brief is read by hand and a second read by two model judges takes the place of a spot check by hand. The page fits one window and never scrolls. The map scales to the space it has and the panels inside each view scroll on their own. Orange on white replaces the mockups' fuchsia and sets the page apart from the site's other projects.

That evening the Code link left the top bar and How it works went to one column. The decay curve now ends where the text does. Its code section opens on its own with a pane that lists the files. It shows excerpts of the real files and never a whole one. Each line keeps the number it has in its file.

Later that night the map learned to zoom and the top accounts became links to their pages. The map zooms up to eight times by its buttons, the wheel, a pinch, or a double-click, and a drag moves it. The bubbles keep their size on the screen and are packed again at each zoom. A cluster spreads toward its true cities as it opens. A region's chip zooms to its accounts and each row of the top ten is a link to its account.

Then the way the map shows the accounts was chosen from three mockups drawn from the real read. One ring per city won over a dot for every account and over clusters that split. A ring sits at its city with its number as the count and its colors as the tiers. A city that holds a top ten account wears a dark ring. Picking a ring lists its accounts, pointing at an account lights up every US city its postings name, and the zoom goes to sixteen times. Placing offices by street was ruled out because the boards name cities only.

## The review pass, November 11

A picked account's footprint became solid dots sized by its open roles there. A caption on the map says what the dots are and the footprint's swatch left the key. A ring that merges several cities now takes the name of the city with the most of its accounts and no label covers a ring's number.

The private list was written again twice that day and six boards left the read. Each time the snapshot was frozen again with no rule changed. Every other account kept its score, its tier, and its place in the order. Two of the six had scored briefs and their records left the public copy with them. From here an account the private list removes leaves the page with its records and the counts follow.

OpenSpace stood in for another dev account in the later dev runs. The prompt was tuned on it and it joined the dev list the same day. An account the prompt was tuned on never counts as scored. That leaves 23 accounts with a brief to write. The scoreboard and the second read are counted over those 23. Nine in ten of 23 rounds up to a bar of 21.

The prompt stage was frozen again the same day for a comment in evals/score.py that pointed at a planning file. The snapshot's new freeze also took a comment change in engine/signals.py. No rule or number changed with either.

## The forward test, November 11

The rules of a test of whether the v1 score predicts revenue operations hiring froze on November 11 before the first weekly read. The code that counts and tests it froze with them in evals/forward.py. The rules are in evals/forward_test.json. The test takes each account's score as the v1 rules gave it on November 9 and checks which accounts opened a new revenue operations role in the next four weeks. Open roles alone are the baseline it has to beat. The result comes after the read of December 6 and the page will state it whichever way it comes out.

The spec's second caveat is wrong about Greenhouse. Its board API gives a first published date beside the last update on every Greenhouse posting in the November 9 read. The test never reads a date and the result can't change. The frozen file stays as it froze and this note stands in place of an edit.

## The data

The terms check on November 9 found every provider's terms silent on a third party reading its public job board API. All three were allowed with the conditions in DATA.md.

Ashby's API host publishes a robots.txt that disallows the job board API and the fetch honors every robots.txt it reads. No Ashby board was read as a result. Lever is read at most once a second to match the crawl delay its board host is reported to set.

The first candidate list held 324 companies. The exclusion list removed 42 of them and 39 more were added by the same rule before any board was read. The first fetch read 152 verified boards, and consumer companies came in at 14, under the floor of 15 the plan set. A second consumer list of 21 was written by the same rule before its own fetch. It leaves out Ashby because no Ashby board can be read.

The Census Bureau's internal point for San Francisco sits offshore near the Farallon Islands. The points for South San Francisco and Alameda fall in the bay. All three would have landed outside California on the map and the build caught that. They sit at their city centers instead and config/city_overrides.csv lists each one with its reason.

## The signal rules, tuning pass 1

A sample of the first snapshot's quoted sentences showed weak precision in the phrase families. Forecasting held about 3 real signals in 8, a new territory about 1 in 8, a CRM move about 2 in 12, and a first hire 2 in 4. Most of the misses were sentences about the candidate ("experience implementing a CRM"), finance or supply chain forecasting, routine territory planning in sales roles, and integrations that named a CRM without moving to one.

The rules changed in one pass. A sentence about the candidate never counts. Forecasting needs a sales or revenue title and a sales word in the same sentence unless the title is a revenue or sales operations role. A new territory means the company itself expanding, opening an office or market, or naming its newest region. A CRM move needs a move or a new CRM tied directly to the CRM. After the change, forecasting held 26 signals, a new territory 34, a first hire 3, and a CRM move 1. Real postings rarely announce a CRM migration in so many words and the page says how many of each family were found. No rule names a company.

## The signal rules, tuning pass 2

The sources of the first dev briefs showed one territory pattern still too loose. Across the snapshot "is expanding" was right about 6 times in 17. The rest were a company growing a team, an organization, or its offerings, and a few were the word with nothing after it. The pattern now passes over those shapes and a test pins each one with made-up text. A new territory fell from 35 signals to 24 and three accounts lost the second signal a brief needs. Tier B now holds 8 accounts and tier D holds 120. Stage 1 froze again on November 10 with the first freeze kept in its history. One account the prompt was tuned on climbed into the top 25. It stays in the dev set and no scored account was used for tuning.

## The model runs

The prompt was tuned in two rounds on six dev accounts and evals/tuning_rounds.json records each round. The third dev run found no unsupported claim in any first draft. Claude Haiku 5.5 ran out of room on two of its six first tries. Its own reasoning counts against the 4,000-token output cap the model layer set. The cap rose to 16,000 tokens for every model before the scored run and a reply cut off at the cap now says so in the repair request. Neither change touches the prompt, the inputs, or the checks, and the dev records keep their results as they were.

## The second read

On November 10 the read by hand was dropped and the planned spot check of ten gave way to a second read by two models. Claude Sonnet 5.5 and GPT-6 Luna each read every scored brief against the full text of the postings it rests on. They mark each part as holding up, overreaching, or wrong. A brief holds up only when both judges say so and that keeps any model from passing its own work alone. The judges are tested on errors planted in copies of the dev briefs. One copy moves a date and another adds a claim no posting makes. Their verdict on the scored briefs counts only when the pair catches nine in ten of those planted errors. The bar is nine in ten of the routed model's 25 briefs holding up with both judges. The judge's prompt and code froze as stage 3 before any judgment was made. The page says that models made this read and that no person did.

The judges read the full text of each posting once. It's cleaned first the way every quote is, and any sentence that names a company on the exclusion list, holds a word on the build's blocked lists, or reads like a message to a model is held back. The dry run held back 172 sentences and each one named an excluded company. No record keeps the text and the run was estimated at about five dollars.

The second read of the first prompt fell short. Only 13 of the routed model's 25 briefs held up with both judges where the bar is 23. The judges caught all 12 planted errors and that means the result counts. The why-now sentences held up about 96 times in 100. Most failures came from the likely priority. It named a problem or a need that no posting states and the dev briefs showed the same. The prompt got a second version as the plan says it must. The judges got three clarifications of their own and both froze again before the next run. The first version's briefs and judgments are kept in an archive that stays out of the public copy.

Version 2 cleared the emails on the dev briefs and left the likely priority overreaching in four of six. Three of those flags came from the prompt's own example service and the model had copied it into briefs whose postings never name it. Version 3 drops the example and names the likely priority as the revenue work the cited postings describe in their own words. The brief says so plainly when the postings describe none. The scored run follows only when at least five of the routed model's six dev briefs hold up with both judges and otherwise the page shows every brief's verdict with the shortfall stated.

Version 3 on dev passed every check on the routed model's six first drafts and no priority named a service its postings don't name. One judge held five of the six and the other held three. Two held up with both. Two of the stricter judge's flags call any likely priority drawn from hiring a guess and that reads the brief's purpose more than its facts. The rest were small and real. The rule set before the run called for five and the tuning stopped there. The prompt froze as version 3 and the scored run went ahead with every brief's verdict shown.

The judges of the second read on version 3's scored briefs caught all 12 planted errors again. 18 of the routed model's 25 briefs held up with both judges where version 1 had 13. The other two models rose from 5 to 16 and from 7 to 13. The bar of 23 still wasn't met. The page shows each brief's verdict with the judges' reasons. How it works and the README state the shortfall in the same words as the numbers.

## The exclusion scan

The scan that drops a quoted sentence naming an excluded company first set aside 349 signals. Most of them came from tool names that hold a company's name. A tool's name is now set aside whole before the scan. Office and cloud products sit in config/vendors.txt for the same purpose without becoming signals. The scan then set aside 92 signals and each one names a company on the list outside any tool's name.

The first scan of the whole public copy flagged a few words in the code's comments, the tests, and both prompts. Each one was reworded with no rule changed. The prompts changed before any brief or judgment was made with them and the judge froze a third time for the wording alone. The name lists that redaction reads ship less the few entries the scans flag and the copy on the build machine keeps them all.

## The relaunch (11/20)

The page was read again on November 20 for its relaunch. The exclusion list was written again from Ryan's files first and it now leaves out more companies. The read kept 150 accounts where November 9 kept 160. No signal rule or weight changed. The snapshot froze a second time for the new read alone. Its places are in config/cities.csv.

The claim checker's word list names a region that shares a word with a company on the list. Regions now sit in config/places.txt as places that never count as a mention. The cities already did. A company that shares the word is still found anywhere else.

Every model call for the relaunch goes through the Claude Code command line on Ryan's Claude plan. No call goes to another maker. Claude Opus 5.5, Claude Sonnet 5.5, and Claude Haiku 5.5 write the briefs. Opus and Sonnet are the two judges. The two judges no longer come from different makers. They're still different models of different sizes and a brief holds up only when both say so. Each cost on the page is the command line's figure for what the call would bill at API prices. The judge froze a fourth time for its docstring alone before any judgment was made with it. The prompts and the gate are unchanged. The November 9 briefs and judgments are in data/ai_runs/archive/read-2026-11-09/.
