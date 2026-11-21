# Every visible word on the Account Signals page

Each `## key` heading starts an entry. The text under it is its value until the next heading. Each paragraph sits on one line because `tools/lint_copy.py` reads this file line by line in the build. Entries whose keys start with `ui.` go to the page's script. Their `{name}` fields are filled in where they're used.

## page.title
Account Signals

## page.subtitle
public hiring signals scored and explained

## page.description
Real companies read from their public job boards and ranked for a seller with every point explained. The page maps where they hire and routes each one to a territory. Models write cited briefs that a checker and two model judges read.

## page.share.alt
The Account Signals map with a ring at each city where the scored accounts hire and the top ten beside it.

## page.noscript
This page needs JavaScript to draw the map and score the accounts.

## page.footer
Every company on this page is real and was read from its own public job board on {date}. None of them is affiliated with this page or endorses it. Nothing here was sent to anyone. No person's details were kept.

## page.dark
Dark mode

## page.skip
Skip to the page

## ui.nav
- map = Map
- list = List
- how = How it works
- tour = Take the tour

## ui.fresh
Read from {boards} public job boards on {date}

## ui.banner.preview
A preview with made-up companies and the stand-in's briefs. It never ships.

## ui.banner.standin
A dry build on the real read with the stand-in's briefs in place of the models' briefs. It never ships.

## ui.map.title
Which accounts to work this month

## ui.map.sub
{n} accounts scored and {a} in tier A

## ui.map.aria
A map of the United States with a ring at each city where accounts post the most roles

## ui.chip.all
All regions

## ui.chip.tierA
Tier A only

## ui.key.tier
Tier {t}

## ui.key.ring
A city and its count

## ui.key.top
Holds a top ten account

## ui.ring.area
{city} area

## ui.ring.count
{n} accounts

## ui.ring.one
{name} · {city} · {score}

## ui.ring.many
{place} · {n} accounts · {name} leads

## ui.ring.tip
{place} · {n} accounts · {name} leads

## ui.fp.many
Hires in {n} US cities. The most roles are in {list}.

## ui.fp.one
Its US roles are all in {city}.

## ui.fp.none
Its postings name no US city.

## ui.fp.roles
{n} open roles

## ui.fp.role
1 open role

## ui.fp.and
and

## ui.fp.caption
{name} hires in {n} US cities. A bigger dot holds more of its open roles.

## ui.fp.caption1
{name} posts all its US roles in {city}.

## ui.zoom.group
Zoom the map

## ui.zoom.in
Zoom in

## ui.zoom.out
Zoom out

## ui.zoom.reset
Show the whole map

## ui.why.title
Why {name} leads

## ui.why.lead
{name} scores {score} with {intent} for intent and {fit} for fit.

## ui.why.signals
Its strongest signals are {list}.

## ui.why.signal
Its strongest signal is {one}.

## ui.why.none
It leads on fit alone because no intent signal is recent enough to count.

## ui.why.fit
It fits as {industry} with {band}.

## ui.why.pair
{a} and {b}

## ui.why.note
The code writes this from the score and never asks a model.

## ui.industry
- software = a software company
- logistics = a logistics company
- manufacturing = a manufacturer
- energy = an energy company
- health care = a health care company
- consumer = a consumer company

## ui.family
- revops = a revenue operations role
- salesops = a sales operations role
- crm = a CRM role
- analytics = an analytics engineering role
- leadership = a sales leadership role
- first_hire = a first hire
- crm_move = a CRM move
- forecasting = a forecasting project
- territory = a new territory
- pace = a go-to-market posting
- stack = a named tool

## ui.when
- published = published {n} days before the read
- created = created {n} days before the read
- today = posted on the day of the read
- one = posted the day before the read
- undated = with no date on its board

## ui.side.top
Top accounts

## ui.side.empty
No account in this region scores yet.

## ui.side.back
Back to the top ten

## ui.card.open
Open the account

## ui.card.score
See the score

## ui.card.why
Why now

## ui.card.priority
Likely priority

## ui.card.inference
an inference

## ui.card.nobrief
Briefs go to the top {n} accounts with at least two intent signals. This one scores without a brief.

## ui.remote.title
Not on the map

## ui.remote.text
{n} accounts name no US city in their postings.

## ui.remote.more
See them in the list

## ui.back
Back to the map

## ui.acct.roles
{n} open roles

## ui.acct.one
1 open role

## ui.acct.hub
most roles in {city}

## ui.acct.nohub
no US city named

## ui.acct.board
Open its job board

## ui.route.line
Routed to {seat} with a first touch due {date}

## ui.route.overflow
Routed to the {territory} overflow queue because its seats hold their share of tier A

## ui.route.nodue
Routed to {seat} with no first-touch deadline for tier D

## ui.tabs
- brief = The brief
- score = The score

## ui.brief.why
Why now

## ui.brief.priority
Likely priority

## ui.brief.inference
an inference

## ui.brief.questions
Questions for a first call

## ui.brief.unknowns
What the postings don't say

## ui.brief.none
This account has no brief. Briefs go to the top {n} accounts with at least two intent signals.

## ui.brief.hint
Point at a sentence to follow its threads to the postings it cites.

## ui.models.title
Written by

## ui.models.routed
routed

## ui.models.first
passed every check on the first try

## ui.models.repaired
passed every check after one repair

## ui.models.review
needs review

## ui.models.cost
{cost} at API prices and {secs} seconds

## ui.models.routedNote
The routed model is the cheapest one that cleared every bar on the practice accounts.

## ui.review.title
Needs review

## ui.review.text
The checks still flag this brief after one repair. Each flag is shown with its sentence.

## ui.read.title
The second read

## ui.read.both
Holds up with both judges

## ui.read.one
One judge flags a part

## ui.read.two
Both judges flag a part

## ui.read.none
Not read yet

## ui.read.note
Claude Opus 5.5 and Claude Sonnet 5.5 read this brief against the full text of its postings and marked each part. No person did.

## ui.read.reasons
Show the judges' reasons

## ui.part
- W1 = Why now 1
- W2 = Why now 2
- W3 = Why now 3
- P = The priority
- E = The email

## ui.verdict
- holds up = holds up
- overreaches = overreaches
- wrong = wrong

## ui.src.title
The sources

## ui.src.note
The postings this brief was written from. Each one is quoted and dated as its board gave it.

## ui.src.board
The board

## ui.src.open
Open the posting

## ui.src.same
same posting as [{k}]

## ui.src.counts
counts toward the score

## ui.touch.title
The first touch

## ui.touch.subject
Subject

## ui.touch.body
Email

## ui.touch.approve
Approve

## ui.touch.edit
Edit

## ui.touch.done
Done editing

## ui.touch.reject
Reject

## ui.touch.reset
Undo my edits

## ui.touch.approved
Approved and not sent. Nothing leaves this page.

## ui.touch.rejected
Rejected. Nothing leaves this page.

## ui.touch.clean
The checks find nothing to flag.

## ui.touch.flagOne
The checks flag one thing.

## ui.touch.flagMany
The checks flag {n} things.

## ui.touch.note
Your edits run through the recorder's own checks as you type. They stay on this page.

## ui.touch.seller
Written for an example seller of revenue operations services with a placeholder for each name.

## ui.score.chart
The score over the last {days} days as postings arrived

## ui.score.chartNote
Each dot marks a posting that counts. A signal fades as it ages and a quiet month lowers the line.

## ui.score.fit
Fit

## ui.score.intent
Intent

## ui.score.total
Score

## ui.score.of
of {max}

## ui.score.formula
{share} of intent plus {rest} of fit

## ui.score.industry
Industry is {industry}

## ui.score.roles
{n} open roles make {band}

## ui.score.us
{us} of {known} placed roles are in the US

## ui.score.cap
Intent stops at {cap}.

## ui.score.rule
Two signals count from each family and up to {pace} postings for hiring pace. Each signal loses half its points every {half} days.

## ui.score.temp
temporary role at half points

## ui.score.route
Routing

## ui.score.tier
tier {t}

## ui.ctl.title
Move the weights

## ui.ctl.share
Intent share

## ui.ctl.half
Half-life

## ui.ctl.days
{n} days

## ui.ctl.points
Points by family

## ui.ctl.reset
Reset the weights

## ui.ctl.note
The list, the map, and every route update as you move these.

## ui.ctl.moved
The weights are moved from their defaults.

## ui.list.title
Every account

## ui.list.sub
{n} accounts from {boards} public job boards read on {date}

## ui.list.allTiers
All tiers

## ui.list.brief
With a brief

## ui.list.tag
Brief

## ui.list.none
No account matches these filters.

## ui.col
- rank = Rank
- name = Account
- hub = Most roles in
- fit = Fit
- intent = Intent
- score = Score
- tier = Tier
- reason = Top reason

## ui.reason.fit
fit alone

## ui.how.title
How it works

## ui.how.lead
Account Signals reads real companies' public job boards to rank which ones a seller should work first. Each company scores on how well it fits that seller and how strongly its postings signal intent. The seller in this example sells revenue operations services. Every point has a reason and a posting behind it. Models write a brief for each of the top accounts. Code checks every claim before two model judges read it again.

## ui.how.sources.title
The sources

## ui.how.sources.text
Every company here was read from its own public job board on Greenhouse or Lever on {date}. No Ashby board was read because its API host's robots.txt disallows the job board API. Each provider's terms were checked on November 9. None of them grants or forbids a read of a public board by a third party. The data notes list the conditions.

## ui.how.excl.title
The exclusions

## ui.how.excl.text
A private list of companies is left out before any board is read. Every build and every export checks it again.

## ui.how.read.title
The read

## ui.how.read.text
The read found {boards} boards with {postings} postings. {placed} of them name a US city. The postings gave {signals} signals. {scoring} of those count toward a score as roles or projects. The rest are hiring pace and the tools that each posting names.

## ui.how.read.people
Before anything was stored the quoted text lost {names} likely names, {emails} email addresses, {phones} phone numbers, {links} links, {handles} social handles, and {tags} recruiter tags that it found anywhere in the full text of the postings it quotes.

## ui.how.score.title
The scoring

## ui.how.score.fit
Fit is up to 100 points from the industry, the number of open roles, and the share of placed roles in the US. The open roles stand in for size.

## ui.how.score.intent
Intent adds points for each signal by its family and halves them every {half} days. Two signals count from each family along with up to {pace} postings for hiring pace. Intent stops at 100 points however many signals come in.

## ui.how.score.total
The score is {share} of intent plus {rest} of fit. The tiers start at 75, 60, and 40. The page and the build run the same arithmetic. {vectors} shared test cases prove that both of them give every account the same score.

## ui.how.score.curve
A signal's points as it ages

## ui.how.route.title
The routing

## ui.how.route.text
Each account goes to a territory by the region where it posts the most roles and by its size. Two seats share a territory with up to three tier A accounts each. The first touch is due in two business days for tier A, five for tier B, and ten for tier C.

## ui.how.ai.title
The briefs and their checks

## ui.how.ai.text
Three Claude models of different sizes wrote a brief for each of the top {n} accounts from the account's own postings and nothing else. Each sentence cites the postings it rests on. A checker then reads every number, date, name, tool, and quote against those postings before a brief can show as checked. A brief that still fails after one repair shows as needing review.

## ui.how.ai.touch
Each first touch speaks for that seller with placeholder names. Nothing on this page is ever sent.

## ui.how.second.title
The second read

## ui.how.second.text
Opus and Sonnet then read every brief against the full text of the postings it rests on and marked each part as holding up, overreaching, or wrong. A brief holds up only when both judges say so. Their read counted only after they caught errors planted in copies of other briefs. They caught {caught} of {planted}. No person read any of the briefs for this check.

## ui.how.second.pass
{held} of the routed model's {of} briefs hold up with both judges against a bar of {need}.

## ui.how.second.miss
{held} of the routed model's {of} briefs hold up with both judges. That falls short of the bar of {need}.

## ui.how.second.none
The second read hasn't run on these briefs yet.

## ui.how.board.title
The scoreboard

## ui.how.board.text
Each model wrote the same {n} briefs from the same sources on a Claude plan. Each cost is the API price of its calls.

## ui.how.board.cols
- model = Model
- first = Passed on the first try
- review = Needs review
- held = Holds up with both judges
- cost = API price a brief
- secs = Seconds a brief

## ui.how.team.title
What a revenue team needs to run this

## ui.how.team.items
- one = Its own account list in place of the companies read here.
- two = Its own weights for fit and for the signal families that matter to it.
- three = Its own territories and seats in the routing rules.
- four = A model key and the same checks on every brief.
- five = A weekly read of the boards on a schedule.

## ui.how.limits.title
What it can't do

## ui.how.limits.items
- one = It sees only what a company posts on its public job board.
- two = A keyword rule sets each signal's family and can be wrong. The briefs trust a posting's own title over the rule.
- three = It never sees a company's headcount.
- four = It knows nobody at any company and contacts no one.

## ui.how.code.title
The code

## ui.how.code.text
These are excerpts of the real files. Every line keeps the number it has in its file. The five below carry the work.

## ui.how.code.files
- owner/fetch.py = The fetcher
- engine/signals.py = The signals
- engine/score.py = The scoring
- engine/route.py = The routing
- engine/claims.py = The brief's checks

## ui.how.code.loading
Loading the code

## ui.how.code.lines
{shown} of its {n} lines

## ui.how.code.tree
The files

## ui.tour.steps
- map = The map|Each ring is a city where accounts post the most roles. Its number is the count. Zoom with the buttons, the wheel, or a pinch to pull a crowded area apart.
- why = The leader|The code writes this sentence from the top account's score and never asks a model.
- top = The top ten|The ten highest scores. Each one opens its account, and pointing at one lights up every city it hires in.
- brief = The brief|Each sentence cites the postings it rests on. Point at one to follow its threads to the quotes.
- read = The second read|Two model judges read every brief against its full postings and marked each part.
- touch = The first touch|Edit the email and the same checks run as you type. Approving marks it approved, and nothing is ever sent.
- score = The score|Every point has its arithmetic and the posting it came from.
- weights = The weights|Move the intent share or the half-life to watch the list, the map, and the routes update live.
- list = The list|Every account the read scored with its top reason. Sort it by any column and filter it by tier or region.
- how = How it works|The sources with their terms, the checks, the scoreboard, and the code.

## ui.tour.next
Next

## ui.tour.back
Back

## ui.tour.close
Close the tour

## ui.tour.count
{i} of {n}

## ui.tab
- map = Map
- account = Account
- score = Score
- how = How

## ui.months
January February March April May June July August September October November December
