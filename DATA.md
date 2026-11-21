# The data behind Account Signals

Where every piece of data comes from, the terms it's used under, and what never leaves the build machine.

## The job boards

Each company's public job board is read through the public API its applicant tracking system offers for that purpose. Three providers are used and no others.

| Provider | Host | What's read | Terms checked | Allowed |
|---|---|---|---|---|
| Greenhouse | boards-api.greenhouse.io | every published job on one company's board, and the board's name | November 9 | with conditions |
| Lever | api.lever.co | every published posting for one company | November 9 | with conditions |
| Ashby | api.ashbyhq.com | every listed posting on one company's board | November 9 | with conditions |

The fetch is an owner script that runs on the owner's machine and never on the page. It reads each board once over HTTPS from these three hosts alone and asks only for the job board paths on each. It reads each host's robots.txt before anything else and skips whatever that file disallows. It pauses between requests, asks Lever at most once a second, and waits longer after a rate limit. It sends a User-Agent that names this project and its repo. It sends no cookies, keys, or personal data. The page shows the snapshot from that one read and the date it was read. It calls nothing.

The terms were checked on November 9 with a research prompt that read each provider's own documentation and terms. Nothing found grants this use or forbids it. Each provider's documents are written for an employer showing its own jobs and none of them binds anyone who isn't a customer.

Greenhouse documents its Job Board API as public ("Job Board data is publicly available") with no key needed to read it. It has no developer terms and no rules on display, storage, or attribution for anyone else. Its robots.txt is reported to disallow only embed paths and the fetch never asks for one. Each posting links to its own page. The page says when a Greenhouse date is a last update and not a first publication.

Lever's Postings API README is written for an employer building its own job site and it warns that published postings "may be scraped by third parties." No term found rules on display, storage, or AI use by anyone else. Its board host's robots.txt is reported to ask for a one-second crawl delay. It's also reported to signal that pages may be indexed, excerpted, and linked but not used to train models. The demo reads Lever at most once a second. It keeps every quote short with a link to its posting and trains nothing. Every company here is a US company and Lever's EU instance isn't read.

Ashby's Job Postings API documentation is written for an organization's own careers page and says nothing about anyone else. The API returns unlisted postings as well. Its documentation says those should be reached only by a direct link and the demo drops every one of them.

No provider has said anything in public about third parties reading these APIs since 2022. Open-source job search tools, hiring research, and commercial data products read all three. The demo reads each board once, links every quote to its posting, and names each provider only as a source. This page isn't affiliated with Greenhouse, Lever, or Ashby or endorsed by them, or by any company it shows.

The documents behind this section are the Greenhouse Job Board API documentation at https://docs.greenhouse.io/job-board.html, the Lever Postings API README at https://github.com/lever/postings-api, and the Ashby Job Postings API documentation at https://developers.ashbyhq.com/docs/public-job-posting-api.

## The read

The boards were read on the evening of November 9 in Pacific time. The page holds 160 verified boards with 9,465 postings. 131 of the boards are on Greenhouse and 29 are on Lever. 7,105 of those postings are in the US and 5,348 name a US city. Ashby's API host publishes a robots.txt that disallows the job board API. The fetch honors it and no Ashby board was read. Ten boards were empty and one didn't name its company. Those were left out.

The postings gave 3,698 signals. 171 count toward a score as roles or projects. The other 3,527 are hiring pace and named tools. Hiring pace counts go-to-market roles. The tools a posting names give a brief its context and score nothing. Before anything was stored, the text lost 1,048 likely names, 2,657 email addresses, 319 phone numbers, 2,134 links, 735 social handles, and 2,886 recruiter tags.

## The account universe

The list of companies was written by one rule before any board was read. Each is a company that sells through a sales team where revenue operations work is plausible and each was thought to post its jobs on one of the three providers. The list spreads across software, logistics, health care, manufacturing, energy, and consumer companies in every region of the country. No company on it was chosen for what it was hiring. A company left the list only when no public board was found for it or its board didn't name it.

## The exclusions

A private list of companies is left out before anything is read. Every build and every export checks again. The list never ships.

## People

No person's data is collected, stored, shown, or sent to a model. Every quoted sentence loses its email addresses, phone numbers, links, social handles, and anything that reads like a person's name before any of it is stored. Each removal is marked where it was. A last scan checks everything that ships for anything that slipped through.

The second read sends the full text of each posting behind a scored brief to two model APIs once. It's cleaned the same way first and any sentence that names a company on the exclusion list is held back. Nothing trains on the text and no record keeps it.

## The map

The state shapes are the Census Bureau's cartographic boundary files as the us-atlas project packages them and they come already projected with Albers USA. The Census Bureau's files are in the public domain and us-atlas is released under the ISC license. City coordinates come from the Census Bureau's Gazetteer national places file. It's in the public domain too and only the places the postings use are kept in `config/cities.csv`. Each company sits at the US city where most of its open roles are and that isn't always its headquarters.

## SEC filings

The SEC's EDGAR system was checked on November 11 with a research prompt that read the SEC's own pages on reaching its data. The SEC treats what it publishes and the filings it holds as public information that anyone may reuse. The page uses no SEC seal or logo and nothing that suggests an SEC or EDGAR business.

An owner script reads EDGAR from the owner's machine and never from the page. Every request names the project, a person, and a contact address in its User-Agent as the SEC asks. The script stays far under the SEC's limit of ten requests a second. A throttled run stops and waits at least ten minutes. It never asks for anything under /cgi-bin because the SEC's robots.txt disallows it. A company without a ticker is matched through the SEC's quarterly Form D data sets and never through its company search.

A Form D lists the people behind an offering by name and address. The script reads each data set in memory and keeps only the offering's own fields. Those are the filing date, the date of first sale, the amount offered, the amount sold, and the industry group. No related person, signer, or recipient is ever saved.

## DNS records

A company's public DNS records were checked on November 11 the same way. No resolver's terms bar a few hundred slow lookups. Tools and research that read these records for named companies are common. The lookups go slowly through the machine's own resolver.

A record that names a vendor shows what a domain's DNS said on the day it was read and never what a company uses. A verification record shows only that a vendor was set up at some point. Vendors such as Microsoft and Adobe say the record may come out after setup. An SPF include or a mail host says more about the mail that flows today. No verification token is stored or shown and only the vendor its prefix names is kept. config/dns_signatures.csv lists every record the page reads with the vendor's own documentation behind it.

## What ships and what never does

The redacted snapshot in `data/snapshot/` ships with the code. It holds each board's link with its count. It also holds each posting's title, place, date, and link. It also holds the short quoted sentences behind the signals but no full description. The boards as read stay in `data/raw/` on the build machine and never ship. Neither does the private exclusion list.

The recorded briefs and the judges' verdicts ship too. Each one was made with the prompt and the judge as they were frozen. A judge's reason can quote a short phrase from a posting and every reason passes the same scans as the quotes before it's stored. Records made with earlier versions of the prompt stay on the build machine.
