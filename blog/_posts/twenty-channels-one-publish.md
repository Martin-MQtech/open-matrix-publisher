---
title: Twenty Channels, One Publish
date: 2026-08-19
description: How Open Matrix Publisher grew its distribution network from 16 to 20 platforms — and the free-API-first rule that keeps the whole thing at zero cost.
tags: [open-source, distribution, api, engineering]
---

One video. One article. Twenty channels. That is the promise of Open Matrix Publisher, and this week the platform count crossed twenty for the first time.

The number itself is not the point — the network is meant to keep growing, and a few channels will inevitably fall away as others join. What matters is the principle that decides *how* each channel gets connected.

## Ten domestic, ten global

The current matrix is split down the middle: ten Chinese platforms and ten international ones. The two halves are wired completely differently.

The domestic ten run on cookie-based automation. You scan a QR code once, the session is stored locally, and publishing reuses that real browser session. Nothing is ever uploaded to us — credentials and cookies live only on your own machine.

The international ten are a mix. Where a platform offers a free official API, we use it directly: Dev.to, WordPress, Telegram, and Pinterest all publish through their own documented endpoints, with zero cost and no scraping. Social platforms without a usable free API get connected through proven open-source paths — Instagram, for instance, publishes through the same mobile API client that the community has battle-tested for years.

## The free-API-first rule

Not every official API is free, and we treat that as a hard boundary.

X has effectively priced out its free tier, and Reddit charges for commercial access — so we do not pay, and we do not integrate them through paid APIs. X still publishes, but through local cookie automation rather than its billing meter. LinkedIn currently has neither a free API nor an automation path that holds up, so it stays on the bench until a sane option exists.

The short version: if a platform wants us to pay for the privilege of posting our own content, we simply wait or go around. There are always more channels.

## Ship it yourself first

There is a discipline underneath all of this that has nothing to do with APIs. New accounts on public platforms are fragile — a fresh account that immediately starts posting automated content is exactly what spam filters are built to catch. We learned that the hard way.

The fix is the same principle this journal is built on: publish where you control the channel first, then distribute. A static site belongs to you. No algorithm, no moderation queue, no risk of losing the archive. The distribution layer is a tool; the content is yours.

One piece of content. Everywhere it belongs. Twenty channels today, more tomorrow — each one free, local-first, and yours to keep.
