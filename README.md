![background (1)](https://github.com/user-attachments/assets/ef126a76-a392-40ee-8abb-7a5b3c344e01)
Background image generated using [Haiper.ai](https://haiper.ai).
# Indica Café Data Analysis
## Project Overview
This project focuses on analyzing the order and menu data from Indica Café to gain insights into customer preferences, menu performance, and order trends. The analysis is structured around three main objectives, and the results are visualized using Python libraries such as Matplotlib, Seaborn, and Plotly.
## Objectives
The project involves exploring two key tables (menu_items and order_details): one that contains details about the menu items and another that stores information on customer orders. Your first step is to explore the menu items table to get an understanding of the new menu. Next, you'll delve into the order details table to analyze customer transactions. In the final step, you’ll combine the data from both tables to draw conclusions on customer preferences and the success of the new menu items.

**Attributes of the `menu_items` table:**
| menu_item_id | item_name    | category | price |
|--------------|--------------|----------|-------|
| 101          | Hamburger    | American | 12.95 |
| 102          | Cheeseburger | American | 13.95 |

**Attributes of the `order_details` table:**

| order_details_id | order_id | order_date | order_time | item_id |
|------------------|----------|------------|------------|---------|
| 1                | 1        | 2023-01-01 | 11:38:36   | 109.0   |
| 2                | 2        | 2023-01-01 | 11:57:40   | 108.0   |

*Note: The `item_id` in the `order_details` table corresponds to the `menu_item_id` in the `menu_items` table.*



## Repository Contents
### 1. `data/`
- **create_restaurant_db.sql**: This SQL file creates the database schema, including the tables for `order_details` and `menu_items`.
- **objective_1.sql**: SQL queries focused on exploring the menu items table, including finding the total number of items, identifying the cheapest and most expensive dishes, and more.
- **objective_2.sql**: SQL queries that explore the order details table, including finding the total number of orders, date ranges, and identifying orders with the most dishes.
- **objective_3.sql**: SQL queries that combine the menu items and order details tables to identify the most and least ordered items, and explore the details of the highest-spend orders.

### 2. `notebooks/`
- **INDICA_CAFE_Analysis.ipynb**: This Jupyter notebook contains Python code for executing the SQL queries, loading data into Pandas DataFrames, and visualizing the results using libraries like Matplotlib, Seaborn, and Plotly.

## How to Use the Project

1. **Running SQL Queries**:  
   Download all the SQL files from the `data/` directory. First, run the `create_restaurant_db.sql` file to create the database and tables. Then, execute the objective-specific SQL files (`objective_1.sql`, `objective_2.sql`, `objective_3.sql`) one by one to perform the respective analyses.

2. **Detailed Analysis**:  
   For a detailed analysis and visualizations, open and run the Jupyter notebook `INDICA_CAFE_Analysis.ipynb` from the `notebooks/` directory. This notebook will execute the SQL queries and provide insights through data visualizations.

## Analysis and Results

### Objective 1: Exploring the Menu

- **Cheapest Dish**: [Edamame](Asian), Price: $5.0
- **Most Expensive Dish**: [Shrimp Scampi](Italian), Price: $19.95
- **Average Price per Category**:
  
![image](https://github.com/user-attachments/assets/23146c34-894e-4aeb-b8a2-987ae78e019f)

Overall, the data suggests that the café’s pricing strategy varies by cuisine, with Italian dishes being the most expensive on average, and American dishes being the most budget-friendly. This pricing structure could reflect the cost of ingredients, preparation complexity, or customer demand for different types of cuisine.
- **Dishes per Category**: A breakdown of the number of dishes available in each category.
![image](https://github.com/user-attachments/assets/962fa1f8-94a2-43cb-9f2f-cc3d300766fb)

The 'Italian' and 'Mexican' categories each have the highest number of dishes, with 9 items available in each. The 'Asian' category follows closely with 8 dishes, while the 'American' category has the fewest, with 6 dishes. This distribution suggests a diverse menu, with particular emphasis on Italian and Mexican cuisines, potentially reflecting customer preferences or strategic menu planning.

### Objective 2: Analyzing Order Trends

- **Total Orders**: 5370
- **Most Popular Order**:

| order_id | total_items |
|----------|-------------|
| 330      | 14          |
| 440      | 14          |
| 443      | 14          |

The above table lists the order IDs that have the highest number of dishes ordered. Each of these orders contains a total of 14 dishes, indicating they are among the largest and most substantial orders placed at Indica Café.
- **Order Trends**: A timeline of the number of orders placed per day.

![image](https://github.com/user-attachments/assets/0c2336ef-6912-4141-8fc6-fe8cb4e2ea19)
The analysis of daily orders at Indica Café reveals a significant range in the number of orders placed each day. The average number of orders per day is approximately 59.67, indicating a steady level of daily activity. The maximum number of orders observed in a single day reached 87, showcasing peak periods of high customer engagement. Conversely, the minimum number of orders per day was 37, highlighting days with lower activity. This variation underscores the café’s fluctuating demand and can inform inventory and staffing decisions to better accommodate customer flow.

### Objective 3: Combining Menu and Order Data

- **Least and Most Ordered Items**:

![image](https://github.com/user-attachments/assets/84d5c465-eb41-4cfd-811d-a13e0ad4c81a)

Based on our analysis of the most and least ordered items at Indica Café, it's evident that popular dishes like the Hamburger, Edamame, Korean Beef Bowl, Cheeseburger, French Fries, and Tofu Pad Thai, each with approximately 600 purchases, are driving significant customer engagement. To capitalize on this trend, we should emphasize these items in our marketing campaigns and consider offering special promotions to further boost their popularity. Conversely, less ordered items such as Chicken Tacos, Potstickers, Cheese Lasagna, and Steak Tacos, which have around 200 purchases each, may require a strategic review. By enhancing their recipes, adjusting pricing, or running targeted promotions, we can work to increase their appeal and sales. This approach will help optimize our menu and ensure we meet diverse customer preferences effectively.
- **Highest Spend Orders**: Detailed analysis of the top spenders, including insights into which categories contributed the most to these orders.

![image](https://github.com/user-attachments/assets/a59fb630-27be-403d-b01f-a0db0afe7cea)
![image](https://github.com/user-attachments/assets/fc27deb1-2cc6-4dcf-a0de-b61c03834c83)
![image](https://github.com/user-attachments/assets/30129153-6130-47d2-98b0-a17595146a02)


The analysis of the highest spend orders at Indica Café highlights a significant preference for Italian cuisine among top spenders. For example, order ID 440 included 8 Italian items, making it the most prominent category in that order, while other orders like 1957 and 2075 also had strong Italian representation with 5 and 6 items, respectively. While customers still enjoy a mix of other cuisines such as American, Asian, and Mexican, Italian dishes consistently appear as a favorite in high-value orders. The aim moving forward should be to capitalize on this trend by promoting Italian dishes further and possibly introducing new offerings or bundles that feature popular Italian items alongside other cuisines. This approach can enhance customer satisfaction while maximizing revenue from the most popular category.

## Conclusion Analysis:

- **Expand Italian Cuisine Offerings**: Italian dishes have proven to be highly popular, particularly in high-value orders. Introducing new Italian menu items or premium variations could capitalize on this trend.
- **Enhance American and Asian Options**: Given the popularity of dishes like the Hamburger, Edamame, and Korean Beef Bowl, adding new American and Asian items could further drive customer engagement.
- **Optimize or Replace Underperforming Dishes**: Items like Chicken Tacos and Potstickers, which have lower sales, should be reevaluated. Enhancing their appeal or replacing them with new alternatives could improve overall menu performance.
- **Targeted Promotions and Seasonal Menus**: Introducing seasonal menus or promotions that highlight popular items and introduce new ones can keep the menu fresh and attract more customers.
- **Strategic Menu Diversification**: By balancing the expansion of popular categories with the optimization of underperforming items, Indica Café can better align with customer preferences and boost sales.

In summary, by strategically expanding the menu to include more Italian dishes and diversifying the American and Asian offerings, while optimizing or replacing underperforming items, Indica Café can continue to meet evolving customer preferences and boost overall sales.













