# Amazon Arbitrage Automation

These are the Python scripts I wrote while freelancing for Amazon sellers (2023-2025). They automate most of the repetitive work in an online arbitrage store: finding products, checking if they're profitable, checking if the seller is even allowed to list them, and handling orders once they come in. Everything goes into Google Sheets so the seller and their team can see it.

It's around 5,000 lines of Python across 40 scripts. It grew one script at a time as clients asked for new things, so it's more of a toolkit than one app.

## Why I built this

My clients buy products from retail and wholesale sites and resell them on Amazon. Before this they were doing everything by hand. They went through supplier catalogs, searched each item on Amazon, worked out fees and pack sizes on a calculator, then copied every new order into a spreadsheet and made labels one by one. That was taking hours every day, so I started automating it piece by piece.

## How it flows

```
Supplier sites -> product list -> Amazon match -> profit/ROI check -> eligibility check -> sheets

New orders -> TOSHIP sheet -> shipping labels -> tracking -> shipped / refunds / inventory cost
```

## What it does

### Finding products

- Scrapes product name, price, link, variation and pack size from 12 supplier sites (Walmart, WebstaurantStore, Bulk Office Supply and others), going through every page of a category.
- Searches for each product on Amazon and grabs the ASIN, title and price of the match.
- `Reg.py` reads pack sizes and variations out of product titles ("Pack of 12", "24 ct", "3-Pack", sizes, colors). This matters a lot, because if you compare a single item with a 12-pack the profit numbers are completely wrong.
- Works out profit and ROI: Buy Box price per unit, minus the FBA fee, referral fee and supplier cost.
- Pulls the product lists of competitor storefronts so the seller can see what others are selling.
- Goes into Seller Central and checks if each ASIN is restricted. If Amazon allows it, the script requests approval automatically. Then it sorts everything into three sheets: ready to sell, approval requested and not eligible.

### Handling orders

- `ToShip.py` reads all unshipped orders from Seller Central (every page), skips the ones already in the sheet and adds the new ones to `TOSHIP`.
- It then opens each order and fills in the shipping details, ship-by and deliver-by dates, supplier link, cost, fees, profit and ROI, and checks stock in the inventory sheets.
- `labels.py` turns the orders marked for labels into a bulk label sheet (address, package size, weight, pack count).
- The tracking scripts check USPS status and update each order.
- Other scripts sync shipped orders and record refunds.
- `InventoryConcepts.py` does FIFO costing. The business had two partners sharing the same stock, so when one partner ships units the other one bought, it works out the borrowed cost for each of them separately.

## Keeping it running overnight

Most of these scripts run for hours with nobody watching, so a lot of the work went into stopping them from breaking:

- If the internet drops, they wait and retry instead of crashing (`SharedFunc.py`).
- Seller Central has dropdowns inside shadow DOM that normal Selenium clicks can't reach, so I select them with JavaScript. The scripts also deal with the extra tabs some actions open.
- Google Sheets has API limits, so rows are written in batches of 10 to 50 instead of one cell at a time.
- Running a script twice won't add the same order twice.
- There's a random wait between searches, and if a CAPTCHA shows up the script pauses until someone solves it.
- No Amazon passwords in the code. The scripts open Chrome and wait for you to log in yourself, OTP included.

## Results

- Saved my client around 50 hours of manual work a week.

## Tech

Python 3.13, Selenium (Chrome), BeautifulSoup, gspread (Google Sheets API), Google service accounts, regex, requests

## Scripts

| Part | Scripts |
|---|---|
| Supplier scraping | `WalmartGet.py`, `Webstaurant.py`, `Products.py`, `Bulkoffice.py`, `KTSupplyW.py`, `YamiGet.py`, `vipbarber.py`, `regowholesale.py`, `pricemaster.py`, `ThriftyWhite.py`, `Youngsga.py`, `EEdistribution.py`, `OTCWebGet.py` |
| Amazon matching | `ReverseSel.py`, `ReverseSoup.py`, `GoogleAmz.py`, `SelSearch.py`, `SoupSearch.py`, `SoupSearch2.py`, `ExtractSel.py`, `ExtractSoup.py`, `AsinExtractFromAmazonLink.py` |
| Parsing and pricing | `Reg.py`, `pack.py`, `PriceTarget.py`, `NoRes.py` |
| Competitor research | `SellersProducts.py` |
| Selling eligibility | `SellerCentralAdd.py`, `SellerCentralAddExtra.py`, `AddSeller.py` |
| Orders | `ToShip.py`, `Extractcount.py`, `Shipped.py`, `Refunds.py` |
| Shipping and tracking | `labels.py`, `Tracking.py`, `TrackingUSPS.py` |
| Inventory | `Inventory.py`, `InventoryConcepts.py` |
| Shared helpers | `SharedFunc.py` |

## How to run it

1. You need Python 3.10+ and Chrome. Install the packages:

   ```bash
   pip install -r requirements.txt
   ```

2. Create a service account in Google Cloud and download its JSON key. Save it in the project folder as `credentials1.json` (it's in `.gitignore`, so it won't get committed). Then share your Google Sheet with the service account's email and give it Editor access.

3. Each script has a config section at the top. Replace the placeholders with your own values:

   | Placeholder | What it's for |
   |---|---|
   | `YOUR_SOURCING_SHEET_ID` | Product research sheet (tabs `sheet1` to `sheet4`) |
   | `YOUR_ORDERS_SHEET_ID` | Orders sheet (tabs `TOSHIP`, `SHIPPED`) |
   | `YOUR_PARTNER_A_ORDERS_SHEET_ID`, `YOUR_PARTNER_B_ORDERS_SHEET_ID` | Each partner's order sheet, used for inventory and refunds |
   | `YOUR_INVENTORY_SHEET_ID` | Purchases and stock |
   | `YOUR_LABELS_SHEET_ID` | Where the bulk labels go |
   | `sender_info` in `labels.py` | Your return address |
   | `SELLER_URLS` in `SellersProducts.py` | Storefronts you want to research |

   The sheet ID is the long code in the sheet's link: `docs.google.com/spreadsheets/d/<SHEET_ID>/edit`

4. Run a script:

   ```bash
   python ToShip.py
   ```

   For anything that uses Seller Central, Chrome opens and waits for you to log in, then it carries on by itself.

## What I'd do differently now

- Put all the settings in one config file instead of at the top of every script.
- Merge the duplicate versions. Some scripts have a Selenium version and a BeautifulSoup version (like `ReverseSel.py` and `ReverseSoup.py`).
- Use Amazon's Selling Partner API where I can instead of reading Seller Central pages.
- Keep the data in a real database and use Google Sheets only for viewing.
- Add tests.

## Note

This was built for real seller operations. Scraping can go against some sites' terms, so use it responsibly.

## Author

Qaisar Khan - [GitHub](https://github.com/QaisarKhan36) - [LinkedIn](https://www.linkedin.com/in/qaisar-khan-dev)
