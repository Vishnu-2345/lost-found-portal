-- ===========================================
-- LOST & FOUND PORTAL - CLEAN SQL SCRIPT
-- ===========================================

-- CREATE DATABASE
CREATE DATABASE IF NOT EXISTS lost_found_portal;
USE lost_found_portal;

-- ===========================================
-- 1. TABLES (DDL)
-- ===========================================

CREATE TABLE user (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(100) NOT NULL,
  email VARCHAR(100) NOT NULL UNIQUE,
  phone VARCHAR(15),
  role ENUM('student','admin') DEFAULT 'student',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE category (
  category_id INT AUTO_INCREMENT PRIMARY KEY,
  category_name VARCHAR(100) NOT NULL
);

CREATE TABLE location (
  location_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  building VARCHAR(100),
  room VARCHAR(50)
);

CREATE TABLE items (
  item_id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  description TEXT,
  brand VARCHAR(100),
  color VARCHAR(50),
  unique_marks VARCHAR(200),
  category_id INT,
  owner_user_id INT,
  status ENUM('Lost','Found') DEFAULT 'Lost',
  date_reported DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (category_id) REFERENCES category(category_id) ON DELETE SET NULL,
  FOREIGN KEY (owner_user_id) REFERENCES user(user_id) ON DELETE SET NULL
);

CREATE TABLE lostreport (
  lost_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  item_id INT NOT NULL,
  location_id INT,
  date_lost DATE,
  status ENUM('Open','Resolved') DEFAULT 'Open',
  reported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE,
  FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
  FOREIGN KEY (location_id) REFERENCES location(location_id) ON DELETE SET NULL
);

CREATE TABLE foundreport (
  found_id INT AUTO_INCREMENT PRIMARY KEY,
  reported_by_user_id INT NOT NULL,
  item_id INT NOT NULL,
  location_id INT NOT NULL,
  date_found DATE NOT NULL,
  status ENUM('Unclaimed','Returned') DEFAULT 'Unclaimed',
  reported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (reported_by_user_id) REFERENCES user(user_id),
  FOREIGN KEY (item_id) REFERENCES items(item_id),
  FOREIGN KEY (location_id) REFERENCES location(location_id)
);

CREATE TABLE claim (
  claim_id INT AUTO_INCREMENT PRIMARY KEY,
  item_id INT NOT NULL,
  claimer_id INT NOT NULL,
  claim_status ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
  claimed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
  FOREIGN KEY (claimer_id) REFERENCES user(user_id) ON DELETE CASCADE
);

CREATE TABLE log_activity (
  log_id INT AUTO_INCREMENT PRIMARY KEY,
  action VARCHAR(100),
  user_id INT,
  item_id INT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE photo (
  photo_id INT AUTO_INCREMENT PRIMARY KEY,
  entity_type VARCHAR(50) NOT NULL,
  entity_id INT NOT NULL,
  url VARCHAR(255) NOT NULL,
  uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ===========================================
-- 2. INSERT STATEMENTS
-- ===========================================

INSERT INTO category VALUES
(1,'Electronics'),
(2,'Documents'),
(3,'Accessories'),
(4,'Stationery'),
(5,'Clothing');

INSERT INTO user VALUES
(1,'Alice Thomas','alice@pes.edu','9876543210','student',NOW()),
(2,'Bob Nair','bob@pes.edu','8765432109','student',NOW()),
(3,'Divya Kumar','divya@pes.edu','6543210987','student',NOW()),
(4,'Evan Dsouza','evan@pes.edu','5432109876','admin',NOW());

INSERT INTO location VALUES
(1,'Library','Main Block','G01'),
(2,'Canteen','Food Court','F02'),
(3,'Auditorium','Central Block','A05'),
(4,'Classroom A101','Academic Block','A101'),
(5,'Parking Lot','North Wing','P02');

INSERT INTO items VALUES
(3,'ID Card','PES ID 23CS702',NULL,NULL,'lanyard torn',2,3,'Lost','2025-09-03 09:15:00'),
(4,'Jacket','Grey hoodie, size M','H&M','Grey','Small PES logo',5,1,'Found','2025-09-04 08:30:00');

INSERT INTO foundreport VALUES
(2,3,3,5,'2025-09-03','Returned','2025-09-03 09:20:00');

INSERT INTO lostreport VALUES
(2,1,4,4,'2025-09-04','Open','2025-09-04 08:35:00'),
(3,1,4,1,'2025-11-04','Open','2025-11-04 15:02:55');

INSERT INTO claim VALUES
(1,3,1,'Approved','2025-10-23 23:12:42'),
(3,4,1,'Approved','2025-10-23 23:12:42');

INSERT INTO log_activity VALUES
(1,'Lost item reported',1,4,'2025-11-04 15:02:55');

INSERT INTO photo VALUES
(1,'Item',1,'https://picsum.photos/201','2025-09-01 01:05:00'),
(2,'Item',3,'https://picsum.photos/202','2025-09-03 09:18:00'),
(3,'User',1,'https://picsum.photos/203','2025-09-01 01:01:00');

-- ===========================================
-- 3. TRIGGERS
-- ===========================================

DELIMITER $$

CREATE TRIGGER after_lostreport_insert
AFTER INSERT ON lostreport
FOR EACH ROW
BEGIN
    INSERT INTO log_activity (action, user_id, item_id)
    VALUES ('Lost item reported', NEW.user_id, NEW.item_id);
END $$

CREATE TRIGGER update_item_status_after_claim
AFTER UPDATE ON claim
FOR EACH ROW
BEGIN
    IF NEW.claim_status = 'Approved' THEN
        UPDATE items SET status='Found'
        WHERE item_id = NEW.item_id;
    END IF;
END $$

DELIMITER ;

-- ===========================================
-- 4. FUNCTIONS
-- ===========================================

DELIMITER $$

CREATE FUNCTION total_pending_claims()
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE cnt INT;
    SELECT COUNT(*) INTO cnt FROM claim WHERE claim_status='Pending';
    RETURN cnt;
END $$

CREATE FUNCTION total_items_reported(uid INT)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE total INT;
    SELECT
        (SELECT COUNT(*) FROM lostreport WHERE user_id=uid) +
        (SELECT COUNT(*) FROM foundreport WHERE reported_by_user_id=uid)
    INTO total;
    RETURN total;
END $$

DELIMITER ;

-- ===========================================
-- 5. STORED PROCEDURES
-- ===========================================

DELIMITER $$

CREATE PROCEDURE get_claims_by_user(IN uid INT)
BEGIN
    SELECT c.claim_id, i.title, c.claim_status, c.claimed_at
    FROM claim c JOIN items i ON c.item_id = i.item_id
    WHERE claimer_id = uid;
END $$

CREATE PROCEDURE get_lost_items_by_category(IN cat_id INT)
BEGIN
    SELECT i.item_id, i.title, i.description, l.date_lost, l.status
    FROM items i JOIN lostreport l ON i.item_id = l.item_id
    WHERE category_id = cat_id AND l.status='Open';
END $$

DELIMITER ;

-- ===========================================
-- 6. REQUIRED QUERIES
-- ===========================================

-- JOIN
SELECT lr.lost_id, i.title, u.full_name, lr.date_lost
FROM lostreport lr
JOIN items i ON lr.item_id = i.item_id
JOIN user u ON lr.user_id = u.user_id;

-- NESTED QUERY
SELECT title FROM items
WHERE category_id = (SELECT category_id FROM category WHERE category_name='Electronics');

-- AGGREGATE
SELECT c.category_name, COUNT(i.item_id) AS total_items
FROM category c LEFT JOIN items i ON c.category_id = i.category_id
GROUP BY c.category_name;

-- FUNCTION CALLS
SELECT total_pending_claims();
SELECT total_items_reported(1);

-- PROCEDURE CALLS
CALL get_claims_by_user(1);
CALL get_lost_items_by_category(2);

