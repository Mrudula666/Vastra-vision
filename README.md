# Vastra Vision

An ML project that looks at a photo of an Indian textile and identifies its traditional style, region and history, and shows which visual features it used to decide.

Phase 1 covers six Vastra (textile) styles. Abharana (jewellery) and Kala (art) come later.

## Styles in Phase 1

| Folder | Style | Region |
|---|---|---|
| `kalamkari` | Srikalahasti Kalamkari | Andhra Pradesh |
| `pochampally_ikat` | Pochampally Ikat | Telangana |
| `mangalagiri` | Mangalagiri Cotton | Andhra Pradesh |
| `banarasi` | Banarasi Silk | Uttar Pradesh |
| `bandhani` | Bandhani | Gujarat / Rajasthan |
| `kanjeevaram` | Kanjeevaram Silk | Tamil Nadu |

## Folder layout

```
vastra-vision/
  cards/            definition card for each style (region, era, technique, visual markers, sources)
  data/
    images/<style>/ training images, one folder per style
    metadata.csv    one row per image: source, license, artifact/craft
  notebooks/        Colab notebooks (training, Grad-CAM)
  src/              app and helper code (Gradio demo later)
```

## Project rules

1. One domain at a time: Vastra first, then Abharana, then Kala.
2. Every style has a definition card before any images are collected.
3. Tag every image as `artifact` (historical object) or `craft` (made today in the traditional style).
4. Clean data only: openly licensed images or our own photos, with the source of every image recorded.
5. Every history fact has a source and is marked `documented` or `tradition`.
6. The model shows a confidence score and says "not sure" when confidence is low. It never claims an exact century from a photo.
7. Credit the regions and craft communities, and mention GI tags where they apply.
8. Start small: about 5–6 styles per domain.

## Road map

- [x] Step 1: definition cards for 6 styles
- [ ] Step 2: collect 100–150 images per style, fill `data/metadata.csv`
- [ ] Step 3: quick no-code baseline (Teachable Machine)
- [ ] Step 4: fine-tune a pretrained vision model in Colab
- [ ] Step 5: Grad-CAM to show which motifs drove each prediction
- [ ] Step 6: Gradio demo on Hugging Face Spaces
