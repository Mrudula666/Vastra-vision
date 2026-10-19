# Image sourcing guide

A photo alone cannot prove a textile is authentic. A power-loom "Banarasi" or a
printed "Kalamkari" can look the same as the real thing in a picture. So in this
project a label is trusted because of **where the image came from**, not because
of how it looks.

## Trust tiers

| Tier | What it is | Why we trust the label | Goes to |
|---|---|---|---|
| **A** | Your own photos or videos of a verified piece, or images a cooperative or weaver sent with permission | You checked the proof: GI tag or logo, Handloom Mark, India Handloom Brand, Silk Mark, or bought from a GI cooperative or state emporium | straight into `data/images/` |
| **B** | Museum catalogue record | Curators recorded the place, culture and technique; the collector only keeps records whose catalogue says "Indian textile" | `data/candidates/`, then review |
| **C** | Open web (Wikimedia Commons) | Nobody verified it; you decide in review | `data/candidates/`, then review |

Anything else (Google Images, Pinterest, shopping sites without permission) is not used.

## Where each style's images will realistically come from

| Style | Museums (tier B) | Verified sources (tier A) |
|---|---|---|
| Kalamkari | good: many painted and dyed cottons and temple hangings (check Srikalahasti vs Machilipatnam) | Srikalahasti artisans, Lepakshi emporium |
| Pochampally Ikat | few (search "telia rumal") | Pochampally weavers' cooperative, Telangana handloom showrooms |
| Mangalagiri | almost none | Mangalagiri weavers' cooperative, APCO showrooms |
| Banarasi | good: brocades and saris | Silk Mark / GI-labelled pieces, UP handloom emporiums |
| Bandhani | good: odhnis and saris | Jamnagar and Kutch artisans, Gurjari emporium |
| Kanjeevaram | some | Co-optex, Kanchipuram silk cooperatives, Silk Mark pieces |

Mangalagiri and Pochampally will depend mostly on tier A, so start there.

## Proof to record (the `--proof` argument)

- photo of the GI tag or GI logo on the label
- Handloom Mark, India Handloom Brand or Silk Mark label
- shop or cooperative bill
- "sent by <cooperative>" for images received with permission

## Museum sources used by `collect_images.py`

| Source | License | Default |
|---|---|---|
| The Met | CC0 (public-domain objects only) | on |
| Cleveland Museum of Art | CC0 | on |
| Art Institute of Chicago | CC0 (public-domain objects only) | on |
| Victoria and Albert Museum | free for non-commercial use | off (`--include-vam`) |
| Wikimedia Commons | CC BY / BY-SA / CC0 / PD only | on |

The V&A has one of the largest Indian textile collections in the world, but its
images are for non-commercial use only. Use it if the project stays
non-commercial.

## Permission message for cooperatives and weavers

**English**

> Namaste. I am building a free educational project called Vastra Vision that
> teaches people to recognise traditional Indian handlooms such as
> [Mangalagiri] and explains their history and the communities who make them.
> May I photograph some of your sarees, or could you share a few photos, to use
> in this project? Your cooperative will be credited by name, and the photos
> will not be sold. Thank you.

**Telugu**

> నమస్తే. నేను "వస్త్ర విజన్" అనే ఉచిత విద్యా ప్రాజెక్ట్ చేస్తున్నాను. ఇది
> [మంగళగిరి] లాంటి సంప్రదాయ చేనేత వస్త్రాలను గుర్తించడం, వాటి చరిత్ర, వాటిని
> నేసే వారి గురించి ప్రజలకు తెలియజేస్తుంది. ఈ ప్రాజెక్ట్ కోసం మీ చీరలను కొన్ని
> ఫోటోలు తీయడానికి అనుమతిస్తారా, లేదా కొన్ని ఫోటోలు పంపగలరా? మీ సంఘం పేరుతో
> క్రెడిట్ ఇస్తాను, ఫోటోలను అమ్మను. ధన్యవాదాలు.
