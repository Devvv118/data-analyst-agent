// Sample questions the user can load with one click, plus the answer we expect.
export const SAMPLES = [
  {
    "id": "sales",
    "title": "Sales analysis (CSV)",
    "summary": "Revenue, top category by profit, profit margin and top region from an attached sales_data.csv",
    "questions": "Analyze the uploaded sales_data.csv file and answer the following questions:\n\n1. Calculate the total revenue (units_sold * unit_price_usd) across all orders.\n2. Which product category generated the highest total profit, and what was that profit amount?\n3. What is the average profit margin (total profit / total revenue) across the entire dataset, as a percentage rounded to two decimal places?\n4. Identify the top performing region by total units sold.\n\nRespond in a smililar format:\n{\n  \"total_revenue_usd\": <number>,\n  \"top_category_by_profit\": {\n    \"category\": \"<string>\",\n    \"total_profit_usd\": <number>\n  },\n  \"overall_profit_margin_percent\": <number>,\n  \"top_region_by_units\": \"<string>\"\n}",
    "expected": "Total Revenue: $102,940.60\nTop Category by Profit: Electronics ($14,315.00)\nOverall Profit Margin: 32.38%\nTop Region by Units: North America (440 total units)",
    "files": [
      {
        "name": "sales_data.csv",
        "type": "text/csv",
        "content": "order_id,date,category,product,units_sold,unit_price_usd,profit_usd,region\n1001,2023-01-15,Electronics,Wireless Headphones,120,89.99,3240.00,North America\n1002,2023-02-01,Electronics,Smart Watch,85,199.99,4250.00,Europe\n1003,2023-02-14,Apparel,Running Shoes,210,65.00,4410.00,North America\n1004,2023-03-05,Electronics,Bluetooth Speaker,95,49.99,1425.00,Asia Pacific\n1005,2023-03-22,Home & Kitchen,Espresso Machine,40,299.99,2399.60,Europe\n1006,2023-04-10,Apparel,Denim Jacket,150,85.00,3825.00,Latin America\n1007,2023-05-18,Home & Kitchen,Air Fryer,110,119.99,3299.70,North America\n1008,2023-06-01,Electronics,Wireless Headphones,200,89.99,5400.00,Asia Pacific\n1009,2023-06-15,Apparel,Running Shoes,180,65.00,3780.00,Europe\n1010,2023-07-04,Home & Kitchen,Blender,130,39.99,1299.68,Latin America"
      }
    ]
  },
  {
    "id": "scrape",
    "title": "Web scraping",
    "summary": "Stock count, average price and priciest book on the first page of Books to Scrape",
    "questions": "Scrape the first page of books from the Books to Scrape sandbox:\nhttps://books.toscrape.com/\n\nAnalyze the 20 books listed on the homepage and answer the following:\n\n1. How many of the 20 books are currently \"In stock\"?\n2. Convert all book prices from GBP (\u00a3) to float values and calculate the average price of a book on this page.\n3. Identify the title and price of the most expensive book on page 1.\n\nRespond in a smililar format:\n{\n  \"in_stock_count\": <number>,\n  \"average_price_gbp\": <number>,\n  \"most_expensive_book\": {\n    \"title\": \"<string>\",\n    \"price_gbp\": <number>\n  }\n}",
    "expected": "In Stock Count: 20 books\nAverage Price: \u00a337.30\nMost Expensive Book: \"Our Band Could Be Your Life: Scenes from the American Indie Underground, 1981-1991\" (\u00a357.25)",
    "files": []
  }
];

export const toFile = (f) => new File([f.content], f.name, { type: f.type });

export const findSample = (questions) => SAMPLES.find((s) => s.questions.trim() === questions.trim());
