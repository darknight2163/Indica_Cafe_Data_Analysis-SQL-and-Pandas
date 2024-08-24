USE restaurant_db; 

-- 1. Combine the menu items and order_details tables into a single table. (since item_id and menu_item_id are same things)
SELECT * FROM order_details od LEFT JOIN menu_items mi
ON od.item_id = mi.menu_item_id;

-- 2. What were the least and most ordered items? What categories were they in?
SELECT item_name,category, COUNT(order_details_id) AS total_purchase
FROM order_details od LEFT JOIN menu_items mi
ON od.item_id = mi.menu_item_id
GROUP BY item_name, category
ORDER BY total_purchase;


SELECT item_name,category, COUNT(order_details_id) AS total_purchase
FROM order_details od LEFT JOIN menu_items mi
ON od.item_id = mi.menu_item_id
GROUP BY item_name, category
ORDER BY total_purchase DESC;

-- 3. What were the top 10 orders that spent the most money?
SELECT order_id, SUM(price) AS total_sale
FROM order_details od LEFT JOIN menu_items mi
ON od.item_id = mi.menu_item_id
GROUP BY order_id
ORDER BY total_sale DESC LIMIT 10;

-- 4. View the details of the highest spend order. What insights can you gather from the results?
SELECT category, COUNT(item_id) AS num_items
FROM order_details od LEFT JOIN menu_items mi
ON od.item_id = mi.menu_item_id
WHERE order_id = 440 # Because this is the highest spend order from (3)
GROUP BY category;

-- 5. View the details of the top 5 highest spend orders. What insights can you gather from the results?
SELECT order_id,category, COUNT(item_id) AS num_items
FROM order_details od LEFT JOIN menu_items mi
ON od.item_id = mi.menu_item_id
WHERE order_id IN (440,2075,1957,330,2675) # Because these are the highest spend order from (3)
GROUP BY order_id,category;