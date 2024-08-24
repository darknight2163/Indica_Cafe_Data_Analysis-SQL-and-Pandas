USE restaurant_db; 

-- 1. Lets view the order_details table.
SELECT * FROM order_details;

-- 2. What is the date range of orders in the table
SELECT MIN(order_date), MAX(order_date) FROM order_details;

-- 3. Find the total number of orders received in this range of date.
SELECT COUNT(DISTINCT(order_id)) FROM order_details;

-- 4. Find the total number of dishes were ordered within this range of data.
SELECT COUNT(*) AS total_dishes FROM order_details;

-- 5. Find the order id having the most number of dishes.
SELECT order_id, COUNT(item_id) AS total_items FROM order_details
GROUP BY order_id
ORDER BY COUNT(item_id) DESC;

-- 6. Find the order id(s) having more than or equal to 13 dishes.
SELECT order_id, COUNT(item_id) AS total_items FROM order_details 
GROUP BY order_id
HAVING total_items>=13;
