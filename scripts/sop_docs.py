"""SOP document bodies for the Quote Generator."""

META = {
    "owner": "Jericho Freight",
    "effective_date": "08/25/26",
    "version": "1.0",
    "department": "Brokerage",
    "assignee": "Santiago Rendon",
}


def _doc(title, objective, glossary, body, definitions):
    out = dict(META)
    out.update(
        title=title,
        objective=objective,
        glossary=glossary,
        body=body,
        definitions=definitions,
    )
    return out


def h1(text):
    return ("h1", text)


def h2(heading, paras, bullets=None, formula=None):
    extra = {}
    if bullets:
        extra["bullets"] = bullets
    if formula:
        extra["formula"] = formula
    if extra:
        return ("h2", heading, paras, extra)
    return ("h2", heading, paras)


def ltl_single():
    return _doc(
        "LTL Single Shipment Quote SOP",
        "Teach any Jericho teammate, even someone brand new, how to build one Less-Than-Truckload quote for one shipment, how the app does the math, what every printed field means, and why that field helps the customer say yes.",
        [
            "1. Our company and this quote type",
            "1.1 What LTL means in kid words",
            "1.2 When to use Single Shipment instead of Tiered",
            "2. How to open the builder",
            "3. Customer name on the quote",
            "4. Load a previous LTL single quote",
            "5. Route / lane fields",
            "6. Cargo profile fields",
            "7. All-in pricing ledger and the math",
            "8. Accessorial checkboxes",
            "9. Analytics fields the customer never types",
            "10. Generate, print, and file name",
            "11. Every output field and customer value",
            "12. What to say out loud",
            "13. Common mistakes",
            "14. Definitions",
        ],
        [
            h1("1. Our company and this quote type"),
            h2(
                "1.1 What LTL means in basic words",
                [
                    "Imagine a giant box truck. If you only have a few boxes, you do not need to rent the whole truck. You share the truck with other people's boxes. That shared ride is called LTL, which stands for Less Than Truckload.",
                    "A pallet is a wooden square that boxes sit on, like a little raft for cargo. The customer pays mostly by how many pallets they send, plus extra fees if the delivery is hard (like a house with no dock).",
                    "This SOP is only for the Single Shipment builder. That builder answers one question: 'What does it cost to move this many pallets, on this lane, this one time?'",
                ],
            ),
            h2(
                "1.2 When to use Single Shipment instead of Tiered",
                [
                    "Use Single Shipment when the customer already knows the pallet count. Example: 'I have 6 pallets going from Medley to Pensacola next Tuesday.'",
                    "Use the Tiered builder when the customer wants a price menu for different sizes, like 1 pallet vs 6 pallets vs 14 pallets, so they can see that bigger shipments get a cheaper price per pallet.",
                    "If you pick the wrong one, the quote will still print, but it will not match the conversation. Always match the tool to the question the customer asked.",
                ],
                bullets=[
                    "Single Shipment = one count, one all-in total, one printed ledger.",
                    "Tiered = four price tiers plus savings and charts.",
                    "Both print with the file name LTL-Q plus the quote number.",
                    "Their Load Previous Quote lists are separate. A tiered quote will not fill this form.",
                ],
            ),
            h1("2. How to open the builder"),
            h2(
                "2.1 Click path",
                [
                    "On the home screen, hover over the LTL button. A small menu pops up. Click Single Shipment Quote. The title at the top should say LTL Single Shipment Quote.",
                    "If you landed on the tiered builder by accident, use the link that says Open Single Shipment Quote.",
                    "Your name and email must already be saved under Change User. If they are not, the app sends you to that screen first. Those two fields print on every quote so the customer knows who to contact.",
                ],
            ),
            h1("3. Customer name on the quote"),
            h2(
                "3.1 Include customer on quote",
                [
                    "Near the top is a checkbox: Include customer on quote. If it is off, the printed page does not show a customer name. That is fine for a blind estimate.",
                    "If it is on, two boxes appear: Customer name and Contact email. Start typing a name. The app looks in your local customer list and can fill the email for you.",
                    "When you generate with the box on, the app also remembers that name on this computer so next time you can pick it faster. This list is yours only.",
                ],
            ),
            h1("4. Load a previous LTL single quote"),
            h2(
                "4.1 The header picker",
                [
                    "Top right you will see Load Previous Quote. This list only shows quotes you already generated in this Single Shipment builder on this computer.",
                    "Click Select a quote, then click a label like LTL-Q12. The form fills itself: cities, ZIPs, pallets, money, checkboxes, and miles if you had them.",
                    "It will not pull FTL, Dray, International, or LTL Tiered quotes. Those live in other lists on purpose so the wrong boxes do not get filled.",
                ],
            ),
            h1("5. Route / lane fields"),
            h2(
                "5.1 Origin and destination",
                [
                    "Origin City and Origin ZIP Code are where the freight starts, like a warehouse door. Destination City and Destination ZIP Code are where it ends.",
                    "ZIP codes are the most important. The app uses them to measure road miles. City names print so the customer recognizes the lane.",
                    "Click Calculate Distance after both ZIPs are filled. The app asks Google for a truck-friendly drive. The miles land in a hidden box called manual_miles. Generate does not call Google again. It uses the miles you already have.",
                    "If Google is not set up, type the miles you trust, or leave miles blank. Some analytics on the output need miles. The dollar total still works without miles.",
                ],
            ),
            h1("6. Cargo profile fields"),
            h2(
                "6.1 Counts, weight, and size",
                [
                    "Number of Pallets is how many wooden rafts are on this shipment. It must be at least 1.",
                    "Total Cargo Weight (lbs) is how heavy everything is together, not per pallet.",
                    "Commodity Value / Pallet ($) is how much one pallet of goods is worth. This is not the freight price. It is used later to estimate how expensive it is to have goods sitting on a truck for extra days (pipeline inventory).",
                    "Pallet Length, Width, and Height are in inches. A normal grocery pallet is about 48 by 40, but this form defaults near 48 x 48 x 48 so you can change it. Size is used to guess density, which is how heavy the freight is for the space it takes. Carriers use density to pick an NMFC class, which can change the real invoice later if the freight is fluffier or denser than you said.",
                ],
                formula=[
                    "Density math (pounds per cubic foot)",
                    "Cubic feet for one pallet = (length x width x height) / 1728. The number 1728 is how many cubic inches fit in one cubic foot, because 12 x 12 x 12 = 1728.",
                    "Total cubic feet = cubic feet for one pallet x pallet count.",
                    "Density = total weight / total cubic feet.",
                    "Tiny example: 6 pallets, 48 x 48 x 48 in, 3000 lb. One pallet is 64 cubic feet. Six pallets are 384 cubic feet. Density is 3000 / 384 = about 7.81 lb per cubic foot. That density maps to an NMFC class in the app's table (around class 100 in this case).",
                ],
            ),
            h1("7. All-in pricing ledger and the math"),
            h2(
                "7.1 The three money boxes",
                [
                    "Linehaul Base Fee is the truck's main ride price, like the taxi fare before extras.",
                    "Fuel Surcharge / FSC is extra money because diesel costs money. You type a dollar amount here on this form, not a percent.",
                    "Quoted Rate / Pallet is a helper. If you type a per-pallet rate and linehaul is empty, the app splits that rate into about 82% linehaul and 18% fuel so the ledger still has two lines. If you already typed linehaul, the printed per-pallet rate is the all-in total divided by pallets, not this helper box.",
                    "The live summary on the form adds linehaul + fuel + checked accessorials while you type so you can see the total before you generate.",
                ],
                formula=[
                    "All-in total for this shipment",
                    "total = linehaul + fuel surcharge + accessorial fees",
                    "price per pallet on the printout = total / pallet count",
                    "Tiny example: linehaul $984, fuel $216, liftgate $75. Total = $1,275. For 6 pallets, price per pallet = $1,275 / 6 = $212.50.",
                    "If you only typed $200 per pallet for 6 pallets and left linehaul at 0, the app estimates total $1,200, then linehaul $984 (82%) and fuel $216 (18%).",
                ],
            ),
            h1("8. Accessorial checkboxes"),
            h2(
                "8.1 Extra work, extra money",
                [
                    "An accessorial is extra work the truck must do. Think of it as paying for a special request, not the main ride.",
                    "Liftgate default $75. A liftgate is a metal shelf on the back of the truck that goes up and down, used when the building has no dock.",
                    "Residential Delivery default $85. Houses and apartments are slower than warehouses.",
                    "Appointment Required default $45. The driver must book a time window instead of rolling up.",
                    "Limited Access default $65. Places like schools, farms, or military gates take extra time.",
                    "You can change each fee before you generate. Unchecked boxes add $0.",
                ],
            ),
            h1("9. Analytics fields the customer never types as prices"),
            h2(
                "9.1 Transit, holding, and class risk",
                [
                    "Transit mean days is the typical number of days this lane takes. If you measured miles, the app can guess days as miles divided by 600, rounded up. 600 miles is about what one driver can legally drive in a day.",
                    "Transit standard deviation is how wobbly the lane is. A small number means 'usually the same.' A big number means 'sometimes late.'",
                    "Desired CSL is the chance you want the freight to arrive by the promised window, like 95 out of 100 times. Buffer days = Z-score for that chance times the wobbly number. That buffer is extra planning days, not extra money on the freight line.",
                    "Annual holding rate defaults to 20%. That is a simple way to say 'money tied up in goods costs about 20% a year.' Daily holding per pallet = commodity value x 0.20 / 365. Pipeline inventory cost = daily holding x days on the truck x pallet count. This shows the customer that slow freight is not free even if the invoice looks cheap.",
                    "Reclassification penalty is a warning dollar amount if the pallet is oversized (longer or wider than 48 inches, or taller than 60). The app may show a higher NMFC class. That is a risk talk, not an automatic add to the total unless you put it in the ledger yourself.",
                ],
                formula=[
                    "Buffer days and pipeline cost",
                    "buffer days = Z(desired CSL) x lane standard deviation",
                    "daily holding per pallet = commodity value per pallet x holding rate / 365",
                    "pipeline inventory = daily holding x mean transit days x pallet count",
                    "Tiny example: $5,000 goods per pallet, 20% holding, 3 days, 6 pallets. Daily holding = 5000 x 0.20 / 365 = about $2.74. Pipeline = 2.74 x 3 x 6 = about $49.32. That is the 'sitting on the truck' cost of the goods, not the freight bill.",
                ],
            ),
            h1("10. Generate, print, and file name"),
            h2(
                "10.1 Buttons and names",
                [
                    "Click Generate Quote. The app checks that pallets are at least 1 and the total is greater than $0. If something is wrong, it stays on the form.",
                    "The printed page title, and the name Chrome offers when you Save as PDF, is LTL-Q plus the quote number. Example: LTL-Q4242. Click Print Quote. Do not rename it to something cute. The Q number is how we find it later.",
                    "The same number is used across modes. The letters in front tell you the mode. LTL-Q10 and FTL-Q10 are different quotes if both number 10 happened in different modes over time. The counter is shared, so usually the numbers just go 1, 2, 3 for the whole app.",
                    "Back to Builder returns you to the form. Load Previous Quote can bring this snapshot back.",
                ],
            ),
            h1("11. Every output field and customer value"),
            h2(
                "11.1 Letterhead and route",
                [
                    "Company name, phone, email, website, DOT, and MC prove who we are. Rep name and email prove who they should call. Quote number is the ticket stub. Dates tell them how long the price is good (30 days on this mode).",
                    "ORIGIN and DESTINATION with city and ZIP answer 'where does it go?' Distance prints when miles were stored. Transit window prints as a range of business days so nobody treats a guess like a guaranteed appointment.",
                ],
            ),
            h2(
                "11.2 Guaranteed All-In Freight Ledger",
                [
                    "This is the money table. Linehaul, fuel, each accessorial, then the total. Customers buy totals they can explain to their boss. Showing the split teaches them why a residential delivery costs more than a warehouse delivery.",
                    "Price per pallet lets them compare this quote to the last one even if pallet counts change.",
                    "Cost per pallet-mile (total / pallets / miles) is a fairness check. If this number is wild compared to similar lanes, you probably mistyped money or miles.",
                ],
            ),
            h2(
                "11.3 Advanced logistics analytics",
                [
                    "NMFC class from density is a 'will the carrier rebill us?' warning. If class looks high, the freight is fluffy. Tell the customer to confirm dimensions.",
                    "Safety / buffer days help operations plan inventory. A customer who needs goods for a store opening cares more about this than a penny on linehaul.",
                    "CO2 estimate uses miles x tons x 0.162 kg per ton-mile. It is a footprint story, not a tax. Only show it if the customer asked about sustainability.",
                    "Pipeline inventory cost turns transit time into dollars of goods sitting still. That is how you sell a slightly faster option without only talking about the freight invoice.",
                ],
            ),
            h1("12. What to say out loud"),
            h2(
                "12.1 Simple pitch",
                [
                    "You can say: 'This is one shared-truck shipment. You are buying space for these pallets, not the whole trailer. The total on the bottom is what you pay if nothing extra happens. Liftgate and house delivery are called out so there are no surprises. The day range is our planning window, not a guaranteed appointment unless we sell a guaranteed service later.'",
                ],
            ),
            h1("13. Common mistakes"),
            h2(
                "13.1 Fix these before you send",
                [
                    "Using Tiered when they already have a count, or Single when they want a menu.",
                    "Forgetting Calculate Distance, then wondering why miles and pallet-mile cost are blank.",
                    "Typing per-pallet rate AND a huge linehaul, then being shocked at the total.",
                    "Leaving Include customer off when the PDF is going to that customer.",
                    "Loading a previous quote from memory instead of the picker, and mixing FTL numbers into LTL.",
                ],
            ),
        ],
        [
            ("LTL", "Less Than Truckload. Many customers share one trailer. You pay for your slice."),
            ("Pallet", "A wooden (or plastic) platform that boxes sit on so a forklift can move them."),
            ("Linehaul", "The main ride price from pickup to delivery, before extras."),
            ("FSC", "Fuel surcharge. Extra money because diesel is not free."),
            ("Accessorial", "Extra service money: liftgate, residential, appointment, limited access."),
            ("NMFC class", "A freight 'difficulty' number from density and handling. Wrong class can change the invoice."),
            ("Density", "Pounds per cubic foot. Heavy-small is denser than light-fluffy."),
            ("CSL", "Cycle service level. How often you want to be on time, like 95%."),
            ("Pipeline inventory", "The dollar cost of goods sitting on a truck instead of on a shelf."),
            ("LTL-Q", "The print file prefix for both LTL single and LTL tiered quotes."),
        ],
    )


def ltl_tiered():
    return _doc(
        "LTL Tiered Quote SOP",
        "Teach any teammate how to build a volume-ladder LTL quote, how each tier and chart is calculated, and how to show a customer that shipping more pallets at once can lower the price per pallet.",
        [
            "1. What a tiered quote is",
            "2. How to open it",
            "3. Customer and previous quotes",
            "4. Route and miles",
            "5. Pricing templates and four tiers",
            "6. How the app picks a tier for a pallet count",
            "7. Analysis settings",
            "8. Scenarios and current vs recommended cost",
            "9. Phantom consolidation",
            "10. EOQ matrix",
            "11. Supply metrics, carbon, and the chart",
            "12. Generate and LTL-Q file name",
            "13. Output fields and customer value",
            "14. Common mistakes",
            "15. Definitions",
        ],
        [
            h1("1. What a tiered quote is"),
            h2(
                "1.1 Kid picture",
                [
                    "Think of a lemonade stand with a sign: 1 cup is $3, a small pitcher is cheaper per cup, a big pitcher is cheaper still. You are not selling one cup. You are selling a menu so the customer can see that buying more at once is a better deal.",
                    "This builder is for customers who ship again and again, or who can combine two small shipments into one bigger one. It is not the best tool for 'I have exactly 6 pallets tomorrow' unless you also want to show them the whole ladder.",
                ],
            ),
            h1("2. How to open it"),
            h2(
                "2.1 Click path",
                [
                    "Home screen, LTL, then Tiered Quote. The header should say LTL Tiered Quote Builder. There is a link to the single shipment builder if you are in the wrong place.",
                ],
            ),
            h1("3. Customer and previous quotes"),
            h2(
                "3.1 Same rules, different memory",
                [
                    "Include customer on quote works like the other modes. Load Previous Quote on this page only lists LTL tiered snapshots. It will not load a single-shipment LTL quote, because the boxes are different (tiers and scenarios vs one pallet count).",
                ],
            ),
            h1("4. Route and miles"),
            h2(
                "4.1 Lane first",
                [
                    "Fill origin city, origin ZIP, destination city, destination ZIP. Click Calculate Distance. Miles are stored and reused on Generate. Miles feed cost per pallet-mile and the carbon story. The four tier prices themselves are numbers you type. The app does not invent the $ per pallet from Google.",
                ],
            ),
            h1("5. Pricing templates and four tiers"),
            h2(
                "5.1 The ladder",
                [
                    "Quick start buttons load Standard, Premium, or Economy starter numbers. You can still edit every box. They are helpers, not laws.",
                    "Tier 1 Small is 1 pallet. This is the most expensive per pallet because the truck still has to show up for a tiny shipment.",
                    "Tier 2 Standard is 2 to 5 pallets.",
                    "Tier 3 Medium is 6 to 10 pallets.",
                    "Tier 4 Large is 11 to 14 pallets (the chart often caps at 14 even though a 53-foot van can hold about 26).",
                    "The form checks that prices step down as volume goes up: Tier 1 should be greater than Tier 2, which should be greater than Tier 3, which should be greater than Tier 4. If they are not, Generate stops you. A ladder that goes up when you buy more would confuse the customer.",
                ],
            ),
            h1("6. How the app picks a tier for a pallet count"),
            h2(
                "6.1 The rule is a staircase, not a blend",
                [
                    "1 pallet uses Tier 1. 2 through 5 use Tier 2. 6 through 10 use Tier 3. 11 and up use Tier 4.",
                    "Shipment cost for a count = that count x the matching per-pallet price. There is no averaging between rungs.",
                ],
                formula=[
                    "Which price applies?",
                    "If pallets = 1, use tier1. If pallets are 2 to 5, use tier2. If pallets are 6 to 10, use tier3. Otherwise use tier4.",
                    "Tiny example: tier1 $360, tier2 $280, tier3 $220, tier4 $180. Eight pallets cost 8 x $220 = $1,760. One pallet costs $360. Fourteen pallets cost 14 x $180 = $2,520.",
                ],
            ),
            h1("7. Analysis settings"),
            h2(
                "7.1 What those extra numbers do",
                [
                    "Requested volume is the pallet count you think they will actually ship. It drives the highlighted point on the chart and the quoted cost saved in history.",
                    "Annual demand is how many pallets they move in a year. It feeds EOQ, which asks 'what size order is cheapest if we also count storage?'",
                    "Max trailer pallets defaults to 26 (a full van). Max chart pallets defaults to 14 so the picture stays readable.",
                    "Transit mean and standard deviation work like the single builder. Sample size is how many past trips we pretend we have. More samples make the day window a bit tighter.",
                    "Carbon baseline trips vs optimized trips is a simple story: if they used to send 2 trucks and now send 1, carbon_reduction_pct = (2-1)/2 x 100 = 50%.",
                ],
            ),
            h1("8. Scenarios and current vs recommended cost"),
            h2(
                "8.1 Three stories on one page",
                [
                    "Each scenario has a title, a description, a recommended pallet count, and an optional current practice (how many shipments of how many pallets they do today).",
                    "Recommended cost = recommended pallets x the tier price for that count.",
                    "Savings vs buying those same pallets at the expensive Tier 1 price = (pallets x tier1) - recommended cost. That is the 'you already saved vs the worst rung' story.",
                    "Current cost, if you filled frequency and pallets per ship, = frequency x pallets per ship x the tier price for that small size. Compare that to one combined shipment to show consolidation.",
                ],
                formula=[
                    "Scenario dollars",
                    "recommended cost = pallets x price_for(pallets)",
                    "savings vs tier 1 = (pallets x tier1 price) - recommended cost",
                    "current cost = current frequency x current pallets per ship x price_for(current pallets per ship)",
                    "Tiny example: 8 pallets at $220 = $1,760 recommended. Same 8 at $360 = $2,880. Savings vs worst rung = $1,120. If they currently ship 2 times with 4 pallets at the 2-5 price $280, current cost = 2 x 4 x 280 = $2,240. Combining to 8 pallets at $220 = $1,760. They save $480 vs their current habit.",
                ],
            ),
            h1("9. Phantom consolidation"),
            h2(
                "9.1 Paying less by shipping a little more",
                [
                    "Sometimes 5 pallets at the 2-5 price costs more than 6 pallets at the 6-10 price. That feels like a trick, but it is real when the per-pallet drop is steep.",
                    "The app checks: cost at the requested count vs cost at the first count of the next cheaper tier. If the next tier's total is lower, it shows phantom consolidation: add a few dummy or real pallets and pay less overall.",
                    "If the next tier would cost more, the warning stays hidden. Do not invent extra pallets unless the customer can actually fill them.",
                ],
                formula=[
                    "Phantom check",
                    "current total = requested quantity x this tier's price",
                    "optimized total = first pallet count of next tier x next tier's price",
                    "Show the tip only if optimized total is smaller. Savings = current total - optimized total.",
                    "Tiny example: 5 pallets at $280 = $1,400. 6 pallets at $220 = $1,320. Shipping one extra pallet is $80 cheaper. Tell the customer clearly: they get more freight on the truck and a lower invoice.",
                ],
            ),
            h1("10. EOQ matrix"),
            h2(
                "10.1 Economic order quantity in kid words",
                [
                    "EOQ asks: if you buy too often, you pay lots of freight. If you buy too much at once, the goods sit in a warehouse and that costs money too. The sweet spot is in the middle.",
                    "The textbook shape is square root of (2 x yearly demand x cost to place/move a shipment / yearly holding cost). The app then rounds to a whole pallet count between 1 and the chart cap, and maps it to a label like Weekly or Monthly.",
                    "If holding cost is zero, the math would say 'ship the maximum every time,' so the app just picks the cap.",
                    "The matrix repeats this for a few weekly storage dollar columns so you can say 'if storage is cheap, bigger orders win.'",
                ],
            ),
            h1("11. Supply metrics, carbon, and the chart"),
            h2(
                "11.1 Numbers on the analytics block",
                [
                    "Cost per pallet-mile uses the cheapest rung: tier4 / miles. That is a 'if they always buy large' efficiency number.",
                    "Utilization percent = chart pallets / max trailer pallets x 100. At 14 of 26, that is about 54%. You can tell the customer there is still room on a full truck if they ever go FTL.",
                    "Consolidation multiplier = tier1 / tier4. If 360/180 = 2, one lonely pallet costs twice as much per pallet as a large shipment.",
                    "The chart plots price for pallet counts 1 through the chart max using the same staircase rule. It is a picture of the ladder.",
                    "CO2 uses the same truck formula as other modes: miles x tons x 0.162. Weight can come from an optional cargo weight field. If missing, it can fall back to pallets x 500 lb.",
                ],
            ),
            h1("12. Generate and LTL-Q file name"),
            h2(
                "12.1 Print",
                [
                    "Generate Quote builds the HTML page. Print Quote sets the document title to LTL-Q plus the number, same as single shipment. Chrome's Save as PDF should offer LTL-Q4242.pdf, not 'LTL Freight Quote - Jericho Freight.'",
                    "Quoted cost stored in history uses requested volume x the matching tier price.",
                ],
            ),
            h1("13. Output fields and customer value"),
            h2(
                "13.1 How to walk the page",
                [
                    "Volume-Based Pricing Structure is the menu. Customers need this to budget next month, not only today.",
                    "Unified Pricing and Consolidation Visualization is the chart. Point at the drop from 1 pallet to 6 pallets with your finger.",
                    "Optimum Shipping Recommendations are the three scenarios. Read the current practice vs recommended cost out loud.",
                    "Advanced Supply Chain Metrics hold transit windows, EOQ, carbon, and phantom tips. Use them with supply-chain buyers. Skip them with a one-time shipper who only cares about Friday's pickup.",
                    "The 30-day validity line means the ladder can change with fuel and capacity. Do not promise forever prices.",
                ],
            ),
            h1("14. Common mistakes"),
            h2(
                "14.1 Watch-outs",
                [
                    "Putting the same dollar amount in every tier. Then the ladder is fake and phantom consolidation will never appear.",
                    "Loading a single-shipment previous quote in your head onto this form. Use this page's picker only.",
                    "Forgetting that 11-14 still uses tier4 even if the trailer could hold 26. If they have 20 pallets, talk FTL instead of stretching this chart.",
                    "Selling phantom extra pallets the customer cannot fill. The math can be true and still be the wrong advice.",
                ],
            ),
        ],
        [
            ("Tier", "A price rung. More pallets, lower price per pallet."),
            ("Consolidation", "Combining small shipments into one bigger shipment."),
            ("Phantom consolidation", "Adding just enough pallets to fall into a cheaper rung and pay less overall."),
            ("EOQ", "Economic order quantity. A sweet-spot size balancing freight cost vs storage cost."),
            ("Utilization", "How full the trailer is. 14 of 26 pallets is about half a van."),
            ("LTL-Q", "Print file prefix shared with the single shipment LTL quote."),
        ],
    )


def ftl():
    return _doc(
        "FTL Quote SOP",
        "Teach any teammate how to quote a full truck, how every dollar and day is calculated, what the printed ledger means, and how to explain why a whole truck can beat shared LTL once the trailer is full enough.",
        [
            "1. What FTL is",
            "2. How to open it",
            "3. Customer and previous FTL quotes",
            "4. Route, miles, notes, and valid until",
            "5. Equipment and load",
            "6. Utilization math",
            "7. Transit days and the 600-mile rule",
            "8. All-in pricing ledger math",
            "9. LTL comparison",
            "10. Carbon",
            "11. Generate and FTL-Q file name",
            "12. Output fields and customer value",
            "13. What to say out loud",
            "14. Common mistakes",
            "15. Definitions",
        ],
        [
            h1("1. What FTL is"),
            h2(
                "1.1 Kid picture",
                [
                    "FTL means Full Truckload. The customer rents the whole truck, like hiring a whole moving van instead of sharing a bus. Nobody else's boxes get mixed in. That usually means faster, simpler, and better care, and it costs more until the trailer is fairly full.",
                    "Use FTL when pallet count is high, freight is heavy, freight is fragile, or the customer hates terminal handling. LTL freight gets touched at terminals. FTL usually goes dock to dock.",
                ],
            ),
            h1("2. How to open it"),
            h2(
                "2.1 Click path",
                [
                    "Home screen, click FTL. Header should say FTL Quote Builder. Change User must already be filled so your name prints.",
                ],
            ),
            h1("3. Customer and previous FTL quotes"),
            h2(
                "3.1 Mode-only memory",
                [
                    "Include customer on quote works like other modes. Load Previous Quote here only lists FTL snapshots labeled FTL-Q plus the number. It will not load LTL or Dray.",
                ],
            ),
            h1("4. Route, miles, notes, and valid until"),
            h2(
                "4.1 Lane boxes",
                [
                    "Origin city, origin ZIP, destination city, destination ZIP. ZIPs are required. Click Calculate Distance. Miles save into a hidden box. Blurring the ZIP fields also tries to refresh miles.",
                    "If you type a flat linehaul and later get miles, the app can fill rate per mile as linehaul / miles. If you type rate per mile, it can fill linehaul as rpm x miles. Last box you edited wins.",
                    "Valid Until defaults to 7 days from today if you leave it blank. FTL spot prices move faster than LTL menus, so the printed quote says it is valid for that many days.",
                    "Notes print on the quote. Use them for temperature, appointments, or 'driver must have a pallet jack.'",
                ],
            ),
            h1("5. Equipment and load"),
            h2(
                "5.1 Pick the right trailer",
                [
                    "Van (V) is a dry box. Default. About 26 pallet spots and 45,000 lb payload.",
                    "Reefer (R) is a fridge on wheels. About 26 spots and 43,500 lb. Extra boxes appear: setpoint in Fahrenheit, continuous run (the motor stays on), and pre-cool ($75 if checked).",
                    "Boxtruck (SB) is a smaller city truck. About 12 spots and 10,000 lb.",
                    "Flatbed (F), Stepdeck (SD), Hotshot (HS), RGN, and Low-boy (LB) are open decks for freight that does not fit in a box. A tarps box appears. Each tarp adds $50.",
                    "Pallet count and total weight (lb) are optional but they unlock utilization and some carbon math. Team drivers checkbox means two drivers sharing the truck so it can keep moving. That halves the drive days in the 600-mile rule.",
                ],
            ),
            h1("6. Utilization math"),
            h2(
                "6.1 How full is the truck?",
                [
                    "Position utilization percent = pallets / equipment spots x 100. Over-positions is true if pallets are greater than spots. Then you need two trucks or a different idea.",
                    "Weight utilization percent = weight / payload x 100. Over-weight is true if you exceed payload. Then you are illegal or you need a heavier setup. Do not quote that as one truck.",
                ],
                formula=[
                    "Fill percent",
                    "position % = pallets / spots x 100",
                    "weight % = pounds / payload pounds x 100",
                    "Tiny example: van, 20 pallets, 30,000 lb. Position % = 20/26 x 100 = 76.9%. Weight % = 30000/45000 x 100 = 66.7%. The truck is space-full before it is weight-full.",
                ],
            ),
            h1("7. Transit days and the 600-mile rule"),
            h2(
                "7.1 Why 600?",
                [
                    "One truck driver is allowed about 11 hours of driving in a work day. At about 55 miles an hour, that is roughly 600 miles. The app uses 600 on purpose so every mode tells the same story.",
                    "Drive days = miles / (600 x number of drivers). Team uses 2 drivers. The result is rounded to one decimal for the mean.",
                    "The printed window is not a hard appointment. It is mean plus and minus a buffer that grows with trip length and equipment type. Reefers and specialty gear get a slightly wider wobble. If this lane has real history in the local database, the app may swap in a history-backed prediction interval instead of the pure mileage guess.",
                ],
                formula=[
                    "Days on the road",
                    "mean days = miles / (600 x drivers)",
                    "Tiny example: 1,200 miles, solo van. 1200/600 = 2.0 days. Team would be 1200/1200 = 1.0 day. Always say this is a planning window, not a promise, unless a guaranteed product is sold separately.",
                ],
            ),
            h1("8. All-in pricing ledger math"),
            h2(
                "8.1 How the total is built",
                [
                    "If you typed a flat linehaul, that number is the linehaul. If not, linehaul = rate per mile x miles. If you typed neither, rate per mile falls back to $2.50.",
                    "Fuel surcharge dollars = linehaul x (fuel percent / 100). A 20 in the box means 20%, not $20.",
                    "Pre-cool adds $75 only on reefer when checked.",
                    "Tarps add $50 times the tarp count, only on open-deck equipment.",
                    "Detention = hours x dollars per hour (default $75). Detention is paying the driver to wait.",
                    "Other accessorials is a free-typed extra dollar amount.",
                    "Continuous run is a temperature story on the form. It is not currently added as an extra percent in the dollar total. Do not tell the customer it changed the invoice unless you put money in linehaul or other accessorials.",
                    "All-in total = linehaul + fuel + extras. Cost per mile = total / miles. Cost per position = total / pallets.",
                ],
                formula=[
                    "All-in total",
                    "linehaul = flat linehaul, or else rpm x miles (rpm default 2.50)",
                    "fuel = linehaul x fsc% / 100",
                    "extras = pre-cool 75 (reefer) + tarps x 50 (open deck) + detention hours x detention rate + other accessorials",
                    "total = linehaul + fuel + extras",
                    "Tiny example: $2,000 linehaul, 20% fuel, $75 pre-cool. Fuel = $400. Total = $2,475. At 1,000 miles, cost per mile = $2.475.",
                ],
            ),
            h1("9. LTL comparison"),
            h2(
                "9.1 When the checkbox is on",
                [
                    "You may type up to three LTL options with a label, a pallet max, and a total. The app builds a table next to this FTL total.",
                    "Savings = cheapest LTL total minus FTL total. Positive savings means FTL is cheaper. Breakeven pallets is a rough 'at this many pallets FTL starts winning' using the cheapest LTL per-pallet rate.",
                    "Only fill this if you actually have LTL numbers. Fake LTL rows teach the wrong lesson.",
                ],
            ),
            h1("10. Carbon"),
            h2(
                "10.1 Footprint",
                [
                    "kg CO2e = miles x short tons x 0.162. Short tons = pounds / 2000. If pounds are missing, the app may use pallets x 500 lb. This is an EPA-style truck factor, not a lab measurement. Use it when the customer asks, not as a scare line.",
                ],
            ),
            h1("11. Generate and FTL-Q file name"),
            h2(
                "11.1 Print",
                [
                    "Generate Quote writes the page and remembers the form for Load Previous Quote. Print Quote names the file FTL-Q plus the number, for example FTL-Q4242.",
                ],
            ),
            h1("12. Output fields and customer value"),
            h2(
                "12.1 Walk the PDF",
                [
                    "Route block: origin, destination, miles, notes. This is 'where and how far.'",
                    "Guaranteed All-In Freight Ledger: every money line plus the total. This is what they pay if the extras you listed happen. Unlisted extras (lumper, extra stop) are not included. Say that out loud.",
                    "Equipment Utilization: fill percents. Customers use this to see they are not buying empty air, or that they are overweight.",
                    "Delivery window: planning days with a percent confidence (usually 90%). Direct, no terminals is the FTL promise versus LTL's extra handling.",
                    "Mode Comparison: only if you entered LTL options. Use it to recommend FTL vs LTL with numbers, not vibes.",
                    "Estimated Footprint: CO2. Optional conversation.",
                    "Validity days: how long this price is good.",
                ],
            ),
            h1("13. What to say out loud"),
            h2(
                "13.1 Simple pitch",
                [
                    "You can say: 'This price is for the whole truck, door to door, no sharing. The bottom line includes fuel and the extras we checked. It is not a blank check for detention if we did not put hours in. The day range is how long the drive should take at about 600 miles a day for one driver.'",
                ],
            ),
            h1("14. Common mistakes"),
            h2(
                "14.1 Watch-outs",
                [
                    "Typing fuel as $20 instead of 20%. Twenty percent of $2,000 is $400. Twenty dollars is $20.",
                    "Quoting 30 pallets on a 26-spot van.",
                    "Leaving miles at 0, then presenting cost per mile as if it were real.",
                    "Checking LTL comparison with empty totals.",
                    "Promising team transit times without checking Team drivers.",
                ],
            ),
        ],
        [
            ("FTL", "Full Truckload. One customer, whole trailer."),
            ("RPM", "Rate per mile. Dollars for each mile the truck drives."),
            ("Detention", "Money for waiting beyond free time."),
            ("Pre-cool", "Running the reefer before loading so the box is already cold. $75 in this app."),
            ("Team", "Two drivers. The truck can move about twice as many miles per day."),
            ("HOS", "Hours of Service. Federal drive-time rules. Why we use 600 miles a day."),
            ("FTL-Q", "Print file prefix for this mode."),
        ],
    )


def drayage():
    return _doc(
        "Drayage Quote SOP",
        "Teach any teammate how to quote a short container move from a port or rail yard, how chassis and accessorials add up, and how to print a DRAY-Q file the customer can understand.",
        [
            "1. What drayage is",
            "2. How to open it",
            "3. Customer and previous dray quotes",
            "4. Direction, container, and steamship line",
            "5. Origin terminal, return terminal, and facilities",
            "6. Miles, prepull warning, and why miles stay off the PDF",
            "7. Linehaul and fuel math",
            "8. Chassis math",
            "9. Accessorial checklist and fees",
            "10. Live totals",
            "11. Generate and DRAY-Q file name",
            "12. Output fields and customer value",
            "13. What to say out loud",
            "14. Common mistakes",
            "15. Definitions",
        ],
        [
            h1("1. What drayage is"),
            h2(
                "1.1 Kid picture",
                [
                    "A ship or a train brings a big metal box (a container) to a yard. Drayage is the short truck ride that takes that box to a warehouse, or back to the yard. It is not a cross-country van load. It is the last (or first) little hop.",
                    "The truck often does not own the metal frame under the box. That frame is a chassis, like training wheels that the box sits on. We usually rent it by the day, with a 2-day minimum in this app.",
                ],
            ),
            h1("2. How to open it"),
            h2(
                "2.1 Click path",
                [
                    "Home screen, click Dray. Header should say Drayage Quote Builder. Origin terminal is required. Generate will refuse without one.",
                ],
            ),
            h1("3. Customer and previous dray quotes"),
            h2(
                "3.1 Memory",
                [
                    "Include customer on quote works like other modes. Load Previous Quote only lists dray snapshots labeled DRAY-Q plus the number. Multiple warehouse stops are remembered as repeating facility boxes.",
                ],
            ),
            h1("4. Direction, container, and steamship line"),
            h2(
                "4.1 The story of the box",
                [
                    "Import means the box is full coming out of the terminal toward the warehouse, then usually empty going back. The PDF labels that Full OUT and Empty IN.",
                    "Export means the truck often picks empty, loads at the shipper, and returns full. Labels flip to Empty PU and Full IN.",
                    "Container is the box size, like 40' ST (standard 40-foot). 20' is shorter. HC is high cube (taller). RF is reefer. Pick what is really on the booking.",
                    "SSL is the steamship line (Maersk, MSC, and so on). No Info is allowed if you do not know yet. Knowing it helps operations, not the dollar math.",
                ],
            ),
            h1("5. Origin terminal, return terminal, and facilities"),
            h2(
                "5.1 Where the truck goes",
                [
                    "Origin terminal is the port or rail yard. Search your local terminal list. You can add a new terminal under Settings, Terminal Locations.",
                    "Return terminal can be the same yard or a different one. If blank, the app reuses origin.",
                    "Facilities are warehouses. You may add more than one. Name, address, city, state, ZIP. Import calls them receivers. Export calls them shippers. Extra stops usually need the Stop-off accessorial.",
                ],
            ),
            h1("6. Miles, prepull warning, and why miles stay off the PDF"),
            h2(
                "6.1 Miles are for you, not the letter",
                [
                    "The form can measure truck miles from origin ZIP through each facility ZIP back to return ZIP. If the first leg is 150 miles or more, the app suggests prepull. Prepull means 'get the box yesterday and park it, because you cannot pull and deliver the same day.'",
                    "The printed quote does not show miles. Customers in this product buy a linehaul plus extras, not a mileage invoice. Do not write miles on the PDF by hand unless the customer asked.",
                ],
            ),
            h1("7. Linehaul and fuel math"),
            h2(
                "7.1 The two big dollars",
                [
                    "Linehaul is the main dray price you type. If you leave it blank, the app can fall back to older turn-economics fields (loaded miles, empty miles, rpm). Most teammates should just type the linehaul they agreed with the carrier.",
                    "Fuel can be a dollar amount or a percent of linehaul. Percent mode: fuel = linehaul x percent / 100. Amount mode: fuel is the dollars you typed.",
                    "The printed fuel line looks like FSC (20% thru 08/31/26). The percent is computed even if you typed dollars, so the customer sees the equivalent percent through the valid-until date.",
                ],
                formula=[
                    "Fuel",
                    "If fsc_mode is percent: fsc = linehaul x fsc_value / 100",
                    "If fsc_mode is amount: fsc = the dollars you typed",
                    "Tiny example: linehaul $450, fuel 20%. FSC = $90. Printed line: FSC (20% thru the valid date).",
                ],
            ),
            h1("8. Chassis math"),
            h2(
                "8.1 Renting the frame",
                [
                    "Chassis days is how many days you will keep the frame. The app will not go below 2 days.",
                    "Standard chassis is $50 per day. If overweight is on, or triaxle is on, the rate becomes $100 per day (triaxle).",
                    "Chassis rental = rate x days.",
                    "Chassis split is $150 each time you must swap frames (common at some rail ramps). You may pick 0, 1, or 2 splits. Split money = 150 x count.",
                    "Chassis subtotal = rental + splits. This always sits in the pricing column even if accessorials are zero.",
                ],
                formula=[
                    "Chassis",
                    "rate = $100/day if overweight or triaxle, else $50/day",
                    "days = max(days you typed, 2)",
                    "rental = rate x days",
                    "splits = $150 x split count (0 to 2)",
                    "Tiny example: 2 standard days + 1 split = $100 + $150 = $250 chassis package. Overweight 2 days with no split = $200.",
                ],
            ),
            h1("9. Accessorial checklist and fees"),
            h2(
                "9.1 Fixed extras in this app",
                [
                    "These amounts are built in. Checking the box adds that fee. Unchecked adds nothing.",
                    "Reefer $150. Hazmat $150. Overweight (OW) $150. Layover $300. Stop-off $125. Pre-Pull $150. Residential $100.",
                    "Overweight also flips chassis to triaxle rate. The 44,000 lb hint is a warning. You still must check the overweight box for the $150 OW fee and the $100/day chassis.",
                    "Tolls and Other are free-typed dollars.",
                    "Quoted total = linehaul + fuel + all accessorial lines + chassis subtotal.",
                ],
                formula=[
                    "Grand total",
                    "quoted total = linehaul + fsc + accessorials + chassis rental + chassis splits",
                    "Tiny example: $450 linehaul + $90 FSC + $150 reefer + $100 chassis (2 days x $50) = $790. Add a $150 split and it becomes $940.",
                ],
            ),
            h1("10. Live totals"),
            h2(
                "10.1 The floating box",
                [
                    "While you click checkboxes, a live total updates. Trust it as a preview. Generate uses the same rules. If live total and PDF disagree, you changed a field after looking. Generate again.",
                ],
            ),
            h1("11. Generate and DRAY-Q file name"),
            h2(
                "11.1 Print",
                [
                    "Generate Quote. If origin terminal is empty, you get an error and no number is burned. Print Quote names the file DRAY-Q plus the number. Old files named only Q4242 were the previous style. Use DRAY-Q now.",
                    "Default validity is 7 days if you left Valid Until blank.",
                ],
            ),
            h1("12. Output fields and customer value"),
            h2(
                "12.1 Walk the PDF",
                [
                    "Quote Details: direction, container, SSL, terminals with Full OUT / Empty IN labels, warehouse names and cities. This is the movie of the box.",
                    "Pricing Details: linehaul, FSC line with percent and thru date, chassis line with type and days, then the total. Customers in dray care that chassis is not a surprise.",
                    "Accessorials section lists each extra. If there are none, that block is quiet. Still say 'no extras in this number' out loud.",
                    "Overweight and hazmat flags on the details side warn operations, not just accounting.",
                ],
            ),
            h1("13. What to say out loud"),
            h2(
                "13.1 Simple pitch",
                [
                    "You can say: 'This is the truck piece from the terminal to your warehouse and back. The total includes fuel and chassis for two days. If the box sits longer, chassis days go up. Prepull, extra stops, and overweight are separate lines so you can see them.'",
                ],
            ),
            h1("14. Common mistakes"),
            h2(
                "14.1 Watch-outs",
                [
                    "Generating without an origin terminal.",
                    "Leaving chassis at 2 days when the customer will keep the box a week.",
                    "Checking overweight weight in pounds but forgetting the overweight checkbox.",
                    "Import vs export labels backwards. The customer will think we are pulling the wrong way.",
                    "Loading an FTL previous quote. You cannot. Use the dray picker.",
                ],
            ),
        ],
        [
            ("Drayage", "Short container trucking between a port or rail yard and a nearby warehouse."),
            ("Chassis", "The wheeled frame under a container. Rented by the day in this quote."),
            ("SSL", "Steamship line. The ocean carrier that owns or operates the box."),
            ("Prepull", "Pulling the box early and parking it because same-day pull and deliver will not work."),
            ("Chassis split", "Swapping chassis, often at a rail ramp. $150 each in this app."),
            ("Triaxle", "A heavier chassis. $100/day here, used with overweight."),
            ("DRAY-Q", "Print file prefix for this mode."),
        ],
    )


def international():
    return _doc(
        "International Quote SOP",
        "Teach any teammate how to build an ocean or cross-border quote, how Incoterms decide who pays which slice, how landed cost and transit legs are added, and how to print an INTL-Q file.",
        [
            "1. What this quote is",
            "2. How to open it",
            "3. Customer on the quote",
            "4. Title, origin text, destination text, pallets, notes",
            "5. Equipment and weight",
            "6. Incoterms 2020 in kid words",
            "7. Landed cost waterfall math",
            "8. Transit legs math",
            "9. Container utilization",
            "10. Lanes and legs you type",
            "11. Generate and INTL-Q file name",
            "12. Output fields and customer value",
            "13. What to say out loud",
            "14. Common mistakes",
            "15. Definitions",
        ],
        [
            h1("1. What this quote is"),
            h2(
                "1.1 Kid picture",
                [
                    "Domestic quotes are one truck. International quotes are a journey with several vehicles: a truck to a port, a ship, maybe customs, then another truck. Each piece is a leg, like chapters in a story.",
                    "This builder lets you skip chapters you do not know yet. You may print a lane picture with only ocean rates, or a full landed-cost stack if the customer gave you duty and VAT.",
                    "There is no Load Previous Quote on this mode. Save the PDF. If you need the same job again, copy from the last PDF or rebuild the lanes.",
                ],
            ),
            h1("2. How to open it"),
            h2(
                "2.1 Click path",
                [
                    "Home screen, click International. Header should say International Quote Builder. Generate is a button that sends JSON, not a normal HTML form post. Stay on the page until the quote opens.",
                ],
            ),
            h1("3. Customer on the quote"),
            h2(
                "3.1 Optional name",
                [
                    "Include customer on quote works the same. There is no previous-quote picker here.",
                ],
            ),
            h1("4. Title, origin text, destination text, pallets, notes"),
            h2(
                "4.1 Words, not only ZIPs",
                [
                    "Quote Title prints as the document heading, like Cartagena International Quote.",
                    "Origin and Destination are free text (city and country). International lanes are not always US ZIP to US ZIP.",
                    "Pallet Count is the example size used to scale per-pallet lane prices into a total.",
                    "Valid Until defaults to 15 days if blank. Ocean rates move. Notes print at the end.",
                    "Route miles override is optional and rarely needed. Most of this quote is not mileage based.",
                ],
            ),
            h1("5. Equipment and weight"),
            h2(
                "5.1 The metal box",
                [
                    "Pick 20' TEU, 40' FEU, 40' High Cube, or a domestic 53' style box if that is truly the move.",
                    "Total weight in kilograms feeds utilization. 1 kilogram is about 2.2 pounds. Do not type pounds in a kg box.",
                ],
            ),
            h1("6. Incoterms 2020 in kid words"),
            h2(
                "6.1 Who pays which chapter?",
                [
                    "Incoterms are three-letter codes that say who pays for which chapter of the journey, and where the risk jumps from seller to buyer. They are not the freight rate. They are the rulebook.",
                    "Check Incoterms 2020 known? only if the customer really named a term. Then pick EXW, FCA, FAS, FOB, CFR, CIF, CPT, CIP, DAP, DPU, or DDP, and whether your customer is the importer (buyer) or exporter (seller).",
                    "EXW: buyer pays almost everything from the seller's door. DDP: seller pays almost everything including duty. FOB is a common ocean middle: seller gets the box on the ship, buyer pays ocean and beyond.",
                    "The app uses that code to show only the cost lines that role pays. If a combo does not make a landed-cost story (for example some exporter + EXW cases), it will say landed cost does not apply.",
                ],
            ),
            h1("7. Landed cost waterfall math"),
            h2(
                "7.1 Stacking dollars in a fixed order",
                [
                    "Check Full landed costs known? only if you have real numbers. Empty boxes are skipped.",
                    "Goods value (FOB) is what the cargo is worth before international add-ons.",
                    "Duty percent and VAT percent are taxes. Dutiable basis CIF means tax is figured on goods + ocean + insurance. FOB basis means tax is figured on goods only.",
                    "The full textbook stack, when used, is: goods, plus ocean, plus insurance, equals CIF. Duty applies to the dutiable basis. VAT applies to (dutiable + duty). Then destination inland.",
                    "The role waterfall only adds the legs that role pays: origin inland (L), origin port (P1), ocean (O), dest port (P2), dest inland (D), plus duty/VAT if that role is the duty payer. DDP is the rare case where the seller pays duty.",
                ],
                formula=[
                    "Duty and VAT (CIF basis)",
                    "CIF = goods value + ocean freight + marine insurance",
                    "duty = dutiable x duty% / 100  (dutiable is CIF, or FOB if you picked FOB basis)",
                    "VAT = (dutiable + duty) x VAT% / 100",
                    "Tiny example: goods $10,000, ocean $2,000, insurance $100, duty 5%, VAT 19%, CIF basis. CIF = $12,100. Duty = $605. VAT base = $12,705. VAT = $2,413.95. Then add any inland you typed.",
                ],
            ),
            h1("8. Transit legs math"),
            h2(
                "8.1 Days you can add, not days we invent from Google",
                [
                    "Check Transit times known? then type days for origin truck, origin port dwell, ocean, dest customs/port, dest truck. If you leave a box blank, that leg can use a built-in default (ocean 18 days, and so on) when the plan runs.",
                    "Total mean days = sum of the legs you included. The wobble is not added as a simple sum. Independent wobbles combine as the square root of (each wobble squared). That is like two wobbly roads that do not always wobble on the same day.",
                    "The printed window is mean plus/minus 1.645 x combined sigma for about 90%. The hint tells you which leg is the widest (often ports).",
                ],
                formula=[
                    "Combined transit",
                    "mean = L + P1 + O + P2 + D (only legs in the plan)",
                    "sigma = square root of (1.0^2 + 2.0^2 + 2.0^2 + 2.5^2 + 0.5^2) when defaults are used, about 4.3 days",
                    "window = mean +/- 1.645 x sigma",
                    "Tiny example: ocean 18, others at defaults. Mean is about 29 days. The window is several days wide. Never sell the low number as a guarantee.",
                ],
            ),
            h1("9. Container utilization"),
            h2(
                "9.1 Will it fit?",
                [
                    "Floor positions: 20' about 9 pallets, 40' about 20, 40' HC about 23, 53' van about 26.",
                    "Cube percent (when the box has a cubic meter rating) = pallets x 2.0 cubic meters / box cubic meters x 100. Two cubic meters is a stand-in for a 48x40 stacked pallet.",
                    "Weight percent = kg / payload kg x 100. If over floor positions, tell the customer they need another box or a different equipment type.",
                ],
            ),
            h1("10. Lanes and legs you type"),
            h2(
                "10.1 Building the picture",
                [
                    "A lane is one path, like Jerome to Oakland to Cartagena. You may add more lanes to compare.",
                    "A leg inside a lane is one chapter with a cost. Add legs until the story is complete. Per-pallet costs on legs get multiplied by the example pallet count on the output.",
                    "Use Add Lane and Add Leg. Remove ones you do not need. Empty lanes make a thin quote.",
                ],
            ),
            h1("11. Generate and INTL-Q file name"),
            h2(
                "11.1 Print",
                [
                    "Click Generate International Quote. If the payload is empty, you get sent back. Print Quote names the file INTL-Q plus the number.",
                    "Preview mode (if used) can skip saving to history. Normal generate saves and may try CRM in the background. Quotes still print if CRM is off.",
                ],
            ),
            h1("12. Output fields and customer value"),
            h2(
                "12.1 Walk the PDF",
                [
                    "Summary: Proposed Lanes is the map in words. Customers use it to see you understood the routing.",
                    "Cost Breakdowns for N pallets is each lane's money. This is the shopping comparison.",
                    "Incoterms block (if known) tells who pays and where risk transfers. This prevents 'I thought you paid ocean' fights.",
                    "Landed cost waterfall (if known) is the tax-inclusive stack. Importers need this for true cost, not just ocean freight.",
                    "Transit plan (if known) is the day range and the wide-leg hint. Operations uses this to set sail dates.",
                    "Container utilization warns about stuffing the box too full or too heavy.",
                    "Validity is usually 15 days unless you set a date.",
                ],
            ),
            h1("13. What to say out loud"),
            h2(
                "13.1 Simple pitch",
                [
                    "You can say: 'This is not one truck price. It is the journey. The Incoterm says which slices are yours. The bottom of the waterfall is the true cost if we included duty and VAT. The day range includes port sitting time, not just sailing days.'",
                ],
            ),
            h1("14. Common mistakes"),
            h2(
                "14.1 Watch-outs",
                [
                    "Checking Incoterms known and leaving the code blank.",
                    "Typing pounds into kilograms.",
                    "Selling DDP without duty numbers.",
                    "Comparing two lanes with different pallet counts.",
                    "Treating the low transit day as a booked vessel cutoff.",
                ],
            ),
        ],
        [
            ("Incoterm", "A three-letter rule for who pays which part of an international move, and where risk jumps."),
            ("FOB / CIF", "FOB is goods value. CIF is goods + ocean + insurance. Duty is often figured on CIF."),
            ("Landed cost", "All-in cost to land the goods, including freight and often duty and VAT."),
            ("Leg", "One chapter: inland, port, ocean, customs, delivery."),
            ("TEU / FEU", "Twenty-foot or forty-foot container units."),
            ("INTL-Q", "Print file prefix for this mode."),
        ],
    )


def settings():
    return _doc(
        "Settings SOP",
        "Teach any teammate how to use the home-page settings cog, why each tool exists, and how those tools change every quote without touching the math of a single mode.",
        [
            "1. Where settings live",
            "2. Change User",
            "3. Customers",
            "4. Terminal Locations",
            "5. SOP's library",
            "6. How settings show up on quotes",
            "7. Maps key in kid words",
            "8. Quote file names across modes",
            "9. Load Previous Quote by mode",
            "10. CRM in the background",
            "11. What never to put in GitHub",
            "12. Common mistakes",
            "13. Definitions",
        ],
        [
            h1("1. Where settings live"),
            h2(
                "1.1 The cog",
                [
                    "On the home screen, top right of the logo bar, there is a gear. That is Settings. Click it. A short menu appears: Change User, Customers, Terminal Locations, SOP's.",
                    "There is no Modes menu in that cog. Modes are the big buttons: FTL, LTL, Dray, International.",
                    "If you have never saved a representative, the app takes you to Change User before you can quote. That is on purpose. Every PDF needs a human name.",
                ],
            ),
            h1("2. Change User"),
            h2(
                "2.1 Your name on the letter",
                [
                    "This screen stores Representative name and Representative email on this computer only (a small file named like rep.json in the app data folder).",
                    "Those two fields print on every quote: LTL, FTL, Dray, International. The customer calls that person, not a generic inbox, unless you typed a generic email on purpose.",
                    "Click Save. You return home. Click Cancel only if a name is already saved.",
                    "Switching users on a shared desktop: type the new name and email and Save. The old name is overwritten. There is no password. Do not leave a teammate's email on the box if you are quoting as yourself.",
                ],
            ),
            h1("3. Customers"),
            h2(
                "3.1 The local phone book",
                [
                    "Customers is a list on this computer, not the whole company CRM. Search by name or email. Pick a row to fill the boxes. Add customer saves a new row. If that name already exists, the button becomes Update.",
                    "On each quote form, Include customer on quote searches this same list. Generating with the box on can add or update the name here.",
                    "Use real spelling. 'Acme' and 'ACME LLC' are two rows if you type them differently. The quote prints whatever you typed.",
                    "Deleting or editing here does not change PDFs you already saved. It only changes the next pick.",
                ],
            ),
            h1("4. Terminal Locations"),
            h2(
                "4.1 The yard list for dray",
                [
                    "Dray quotes need a real terminal name. This screen is where you add yards: name, address, city, state, ZIP.",
                    "Search the list to edit an existing yard. For a brand new yard, type in Terminal Name. Google can suggest a place. Address is not the Google search box. Name is.",
                    "Save puts the yard into the local list (and can sit beside a shared terminals file). Dray origin search uses this list. If the yard is missing, you will fight the required origin terminal field all day.",
                    "Do not invent a ZIP. Chassis and miles tools need a real postal code.",
                ],
            ),
            h1("5. SOP's library"),
            h2(
                "5.1 These PDFs",
                [
                    "SOP's opens a page that lists the six how-to files, including this one. Open or download a PDF. They live in the app's sops folder so they can ship on GitHub and inside the Windows install.",
                    "If a file is missing, rebuild them with python scripts/build_sops.py after reportlab is installed. Do not replace them with Word drafts that skip the math sections.",
                ],
            ),
            h1("6. How settings show up on quotes"),
            h2(
                "6.1 The chain",
                [
                    "Change User -> letterhead contact.",
                    "Customers -> optional customer name/email on the PDF when the checkbox is on.",
                    "Terminal Locations -> dray origin and return search.",
                    "SOP's -> training. They do not change prices.",
                    "None of these screens change linehaul math. If a total is wrong, fix the quote form, not Settings.",
                ],
            ),
            h1("7. Maps key in kid words"),
            h2(
                "7.1 How the app knows miles",
                [
                    "Calculate Distance asks Google 'how far does a truck drive?' Google only answers if this computer has a Maps key in config.json. That file is local. It is not committed to GitHub.",
                    "If the key is missing, distance buttons explain that. You can still type miles by hand in modes that allow it, or quote dray on dollars only.",
                    "Generate does not call Google again. It uses miles already stored. That keeps quoting fast.",
                ],
            ),
            h1("8. Quote file names across modes"),
            h2(
                "8.1 The Q rule",
                [
                    "Every quote gets a number from one shared counter. The print name adds letters so you know the mode.",
                    "FTL-Q4242, LTL-Q4242 (single or tiered), DRAY-Q4242, INTL-Q4242. Click Print Quote. Chrome Save as PDF should offer that name. If you save as 'quote.pdf' you will lose it on the desktop.",
                ],
            ),
            h1("9. Load Previous Quote by mode"),
            h2(
                "9.1 Separate cookie jars",
                [
                    "FTL, LTL single, LTL tiered, and Dray each remember their own last quotes on this computer. International does not. A picker never mixes modes, so you cannot spill chassis days into an FTL van quote.",
                    "These history files are local. They are not for GitHub.",
                ],
            ),
            h1("10. CRM in the background"),
            h2(
                "10.1 Twenty",
                [
                    "If a CRM key is saved, the app tries to tell Twenty about the quote after Generate. If Twenty is not running, the quote still prints. You may see a short line that CRM is not running. That is not a failed quote.",
                    "Do not wait on CRM to send the PDF to the customer.",
                ],
            ),
            h1("11. What never to put in GitHub"),
            h2(
                "11.1 Secrets stay local",
                [
                    "Do not commit config.json, API keys, customer dumps, terminal dumps, quote history JSON, or quote_counter.json. The sops PDFs are allowed. They have no secrets.",
                ],
            ),
            h1("12. Common mistakes"),
            h2(
                "12.1 Watch-outs",
                [
                    "Quoting under someone else's saved name.",
                    "Adding a terminal with a fake ZIP.",
                    "Looking for SOPs under Modes. They are under the cog.",
                    "Thinking Customers is the company CRM of record.",
                ],
            ),
        ],
        [
            ("Settings cog", "The gear on the home screen. Change User, Customers, Terminal Locations, SOP's."),
            ("Representative", "The person whose name and email print on quotes."),
            ("Local catalog", "A list saved on this computer, not the whole company database."),
            ("config.json", "Local settings file for Maps and CRM. Not for GitHub."),
            ("Q prefix", "FTL-Q, LTL-Q, DRAY-Q, INTL-Q printed file names."),
        ],
    )


def all_sops():
    return [
        ("SOP-LTL-Single-Shipment.pdf", ltl_single()),
        ("SOP-LTL-Tiered.pdf", ltl_tiered()),
        ("SOP-FTL.pdf", ftl()),
        ("SOP-Drayage.pdf", drayage()),
        ("SOP-International.pdf", international()),
        ("SOP-Settings.pdf", settings()),
    ]
