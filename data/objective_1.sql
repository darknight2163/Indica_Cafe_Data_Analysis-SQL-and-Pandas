USE restaurant_db; 

-- 1. Lets view the menu_items table.
SELECT * FROM menu_items;

-- 2. Total number of menu items in the table.
SELECT COUNT(*) AS total_items FROM menu_items;

-- 3. Find the most cheaper and expensive dishes from the menu.
SELECT * FROM menu_items 
ORDER BY PRICE LIMIT 1; 

SELECT * FROM menu_items 
ORDER BY PRICE DESC LIMIT 1; 

-- 4. Find the total number of Italian dishes on the menu.
SELECT COUNT(*) AS total_italian FROM menu_items 
WHERE category='Italian';

-- 5. Find the most cheaper and most expensive Italian dishes from the menu.
SELECT * FROM menu_items 
WHERE category='Italian' ORDER BY PRICE LIMIT 1; 

SELECT * FROM menu_items 
WHERE category='Italian' ORDER BY PRICE DESC LIMIT 1; 

-- 6. Find the number of dishes per category.
SELECT category, COUNT(menu_item_id) AS total_dishes FROM menu_items 
GROUP BY category;

-- 7. Find the average price of each category dish.
SELECT category, AVG(price) AS avg_price FROM menu_items 
GROUP BY category;





