


CREATE TABLE Users (
    user_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('Admin', 'Manager', 'Staff', 'Customer') NOT NULL
);


CREATE TABLE CheckInCheckOut (
    record_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    booking_id INT(11) NULL,
    check_in_time DATETIME NULL,
    check_out_time DATETIME NULL
);


CREATE TABLE Bookings (
    booking_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id INT(11) NULL,
    room_type VARCHAR(50) NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    status ENUM('Pending', 'Approved', 'Rejected') NULL,
    total_cost DECIMAL(10,2) NULL
);



CREATE TABLE Fees (
    fee_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    fee_type VARCHAR(50),
    fee DECIMAL(10,2)
);


CREATE TABLE Services (
    service_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    booking_id INT(11),
    service_type VARCHAR(50),
    fee DECIMAL(10,2),
    status ENUM('Requested', 'Completed')
);



-----------------------------------------------------------------------------------

CREATE TABLE RoomFees (
    room_type VARCHAR(50) NOT NULL PRIMARY KEY,
    fee DECIMAL(10,2) NOT NULL
);


INSERT INTO RoomFees (room_type, fee) VALUES ('Deluxe', 150.00);
INSERT INTO RoomFees (room_type, fee) VALUES ('Standard', 100.00);
INSERT INTO RoomFees (room_type, fee) VALUES ('Suite', 250.00);




CREATE TABLE PredefinedServices (
    service_id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    service_type VARCHAR(50) NOT NULL UNIQUE,
    fee DECIMAL(10,2) NOT NULL
);


INSERT INTO PredefinedServices (service_type, fee) VALUES ('Food', 20.00);
INSERT INTO PredefinedServices (service_type, fee) VALUES ('Cleaning', 10.00);
INSERT INTO PredefinedServices (service_type, fee) VALUES ('Laundry', 15.00);



CREATE TABLE RoomAvailability (
    room_type VARCHAR(20) NOT NULL PRIMARY KEY,
    available_rooms INT(11) NOT NULL
);



INSERT INTO RoomAvailability (room_type, available_rooms) VALUES ('Deluxe', 14);
INSERT INTO RoomAvailability (room_type, available_rooms) VALUES ('Standard', 13);
INSERT INTO RoomAvailability (room_type, available_rooms) VALUES ('Suite', 12);







