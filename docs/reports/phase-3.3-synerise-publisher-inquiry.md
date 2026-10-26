# Synerise dataset publisher inquiry — unsent draft

Status: **Draft only. Not sent; no GitHub issue created.**

To: recsyschallenge@synerise.com

Contact source: [official repository README](https://github.com/Synerise/recsys2025/blob/e91c1a62f84611151a399ce157e6031a4a73618f/README.md).

Subject: Original Synerise dataset: event counts, timestamp timezone and intended research version

Hello Synerise RecSys Challenge team,

We are assessing the original dataset for a noncommercial e-commerce analytics
portfolio studying behavioral funnels and 14-day repeat purchasing. We downloaded
the original archive linked at https://recsys.synerise.com/data-set:

`https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz`

Archive size: 2,062,884,710 bytes.
SHA-256: `e90b8fded8bc7a87b8c51ced7d5eead75f6deb09852ea701f5f22934e78b66e7`.

Direct counts of its five event Parquet files total 225,224,262 rows, compared with
168,900,513 in the published repository reference:

| Event | Published reference | Downloaded file |
| --- | ---: | ---: |
| page_visit | 150,713,186 | 199,451,980 |
| search_query | 9,571,258 | 13,223,769 |
| add_to_cart | 5,235,882 | 7,541,117 |
| remove_from_cart | 1,697,891 | 2,688,894 |
| product_buy | 1,682,296 | 2,318,502 |

Could you please clarify:

1. Why do the counts differ? Do the reference counts describe a different release,
   time range or filtered population? Is there a version identifier, release note
   or official checksum for the current original archive?
2. Which timezone do the timezone-free timestamp strings represent? Is one common
   clock used across all five event types, and how are daylight-saving transitions
   handled?
3. Were timestamps rounded, truncated, shifted or otherwise anonymized? About
   96.7% of event timestamps have seconds divisible by five. The observed range
   starts on June 23, 2022 around 00:10 and ends on December 8 around 00:09;
   is there a documented preparation rule behind these boundaries?
4. Is the archive identified above the intended original dataset for independent
   academic or noncommercial research, under the published CC BY-NC 4.0 license?

We have preserved the raw records and have not assumed that product-buy rows are
orders or that the timestamps are UTC. We would appreciate any preparation notes
that help us document these limitations accurately.

Thank you.
