import mysql.connector
import getpass
import pymongo
import json
from datetime import datetime, timedelta
# cahe service request made by customer
from bson.objectid import ObjectId

# mongodb conneciton to hotel 
dbconnection = pymongo.MongoClient("mongodb+srv://new-user:asd123@atlascluster.ruyexmq.mongodb.net")
db = dbconnection["hotel"]

# booking room collection
dbcollection_room_booking = db["room_booking"]
dbcollection_booking_status = db['booking_status']
dbcollection_check_in_and_check_out = db['CheckInCheckOut']
dbcollection_service_request = db['service_request']
dbcollection_fee = db['Fee']

#booking_room_list = []

def get_mysql_connection():
    try: 
        connection = mysql.connector.connect(
            host='127.0.0.1',
            user='mgs_user',
            password='habib',
            database='hotelDB'
        )
        return connection
    except Exception as error: 
        print(f'Error while connecting to database: {error}')
        

def setup_database():
    connection = get_mysql_connection()
    cursor = connection.cursor()
    try:
        with open('hotel_setup.sql', 'r') as file:
            setup_script = file.read()
        # excutes the content of the 
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        connection.close()

        
# User register
def register(): 
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        #check if the user is unique
        
        while True: 
            username = input("Please enter a username for register: ")
            password = input("Please enter a password register: ")
            role = input("Please enter your role (Manager, Staff, Customer): ")
            
            if role not in ["Manager", "Staff", "Customer"]: 
                print("\nPlease enter a valid choice")
                continue
            
            cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
            if cursor.fetchone():
                print("Username already exists. Please choose a different username.")
                continue

            # Store new user into SQL
            insert_data_query = """
                INSERT INTO Users (username, password, role) VALUES (%s, %s, %s)
            """
            cursor.execute(insert_data_query, (username, password, role))
            connection.commit()
            print("Successfully created account")
            break 

    except mysql.connector.Error as error: 
        print(f'Error while registering: {error}')
    finally: 
        cursor.close()
        connection.close()
        

# User login 
def login(): 
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        username = input("Please enter username for login: ")
        password = input("Please enter password for login: ")
        
        select_query = ("SELECT * FROM Users WHERE username = %s")
        
        cursor.execute(select_query, (username,))

        user = cursor.fetchone()
        
        if username == user[1] and password == user[2]: 
            print("Sucessfuly logined in")
            # return the data as a dict
            return {"user_id": user[0], "username": user[1], "password": user[2], "role": user[3]} 
        else: 
            print("Invalid Information")
            return None
    except Exception as error: 
        print(f'Error while getting login: {error}')
    finally: 
        cursor.close()
        connection.close()


# cache booking details into mongo collection
def cache_booking_room(user_id, booking_id, room_type, start_date, end_date, status ): 
    try:
        booking = {
            "user_id": user_id, 
            "booking_id": booking_id,
            "room_type": room_type,
            "start_date": start_date, 
            "end_date": end_date, 
            "status": status
        }
        
        dbcollection_room_booking.insert_one(booking)
        print("Added booking into collectiong")
    except Exception as error: 
        print(f'Error occured while cacheing booking details: {error}')
  
 
# books room for user and caches also for quick access
# store and updates the available room count - Standard, Delux and suite
def book_room(user):
    if user['role'] != 'Customer':
        print("Access denied")
        return
    
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        room_type = input("Please enter a room type (Standard, Deluxe, Suite): ")
        start_date = input("Please enter a start date (YYYY-MM-DD): ")
        end_date = input("Please enter an end date (YYYY-MM-DD): ")
        user_id = user['user_id']
        
        # Fetch the fee for the selected room type
        fee_query = """
            SELECT fee
            FROM RoomFees
            WHERE room_type = %s
        """
        cursor.execute(fee_query, (room_type,))
        result = cursor.fetchone()
        
        if not result:
            print("Invalid room type")
            return
        
        room_fee = result[0]
        
        try:
            # Calculate the total cost based on the number of days
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return
        
        if start_date >= end_date:
            print("Start date must be before end date.")
            return
        
        num_days = (end - start).days
        
        # if customer enter check out for same day
        # they will be charge a full day amount not half
        if num_days == 0: 
            num_days = 1
        
        total_booking_cost = num_days * room_fee
        
        print(f"Room Fee per Night: ${room_fee:.2f}")
        print(f"Total Cost for {num_days} days: ${total_booking_cost:.2f}")
        
        # Insert the booking into the Bookings table
        insert_query_booking = """
            INSERT INTO Bookings (user_id, room_type, start_date, end_date, status, total_cost) 
            VALUES (%s, %s, %s, %s, 'Pending', %s)
        """
        cursor.execute(insert_query_booking, (user_id, room_type, start_date, end_date, total_booking_cost))
        booking_id = cursor.lastrowid  # Get the last inserted booking ID
        
        # Create invoice for the booking (initially with zero room service cost)
        #insert_query_invoice = """
            #INSERT INTO Invoice (booking_id, total_booking_cost, total_room_service_cost, grand_total)
            #VALUES (%s, %s, 0.00, %s)
        #"""
        #cursor.execute(insert_query_invoice, (booking_id, total_booking_cost, total_booking_cost))
        
        #cache current fees
        cache_fees(booking_id, "booking_fee", total_booking_cost)
        
        insert_query_fee = """
            INSERT INTO Fees(fee_type, fee)
            VALUES(%s, %s)
        """
        
        cursor.execute(insert_query_fee, ("booking_fee", room_fee))
        
        # Store data into MongoDB for caching
        cache_booking_room(user_id, booking_id, room_type, start_date, end_date, 'Pending')
        
        #Updating the current count of type room available by 1        
        update_room_availability(room_type, -1)
        
        connection.commit()
        print("Booking and invoice successfully created.")
    
    except Exception as error:
        print(f'Error while booking: {error}')
        connection.rollback()
    
    finally:
        cursor.close()
        connection.close()
        

#MANAGER - generates the activity report for the current day
# param is current date.now
def generate_daily_activity_report(date):
    try:
        # Define the start and end of the day
        start_of_day = datetime.combine(date, datetime.min.time())
        end_of_day = datetime.combine(date, datetime.max.time())

        # Calculate total booking revenue for the day
        booking_pipeline = [
            {"$match": {"fee_type": "booking_fee"}},
            {"$group": {"_id": None, "total_booking_revenue": {"$sum": "$fee"}}}
        ]
        total_booking_revenue_result = list(dbcollection_fee.aggregate(booking_pipeline))
        total_booking_revenue = total_booking_revenue_result[0]['total_booking_revenue'] if total_booking_revenue_result else 0

        # Calculate total room service revenue for the day
        service_pipeline = [
            {"$match": {"request_time": {"$gte": start_of_day, "$lt": end_of_day}}},
            {"$group": {"_id": None, "total_room_service_revenue": {"$sum": "$fee"}}}
        ]
        total_room_service_revenue_result = list(dbcollection_service_request.aggregate(service_pipeline))
        total_room_service_revenue = total_room_service_revenue_result[0]['total_room_service_revenue'] if total_room_service_revenue_result else 0

        # Calculate total revenue (grand total) for the day
        total_revenue = total_booking_revenue + total_room_service_revenue

        # Print the financial report for the day
        print("\nFinancial Report for", date.strftime('%Y-%m-%d'))
        print("-"*50)
        print(f"Total Booking Revenue: ${total_booking_revenue:.2f}")
        print(f"Total Room Service Revenue: ${total_room_service_revenue:.2f}")
        print(f"Total Revenue (Grand Total): ${total_revenue:.2f}")

    except Exception as error:
        print(f'Error occurred while generating financial report: {error}')



#Get the current user booking id baed on user name
def get_current_user_booking_ids(username):
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        query = """
            SELECT booking_id 
            FROM Bookings
            WHERE user_id = (SELECT user_id FROM Users WHERE username = %s)
        """
        
        cursor.execute(query, (username,))
        bookings = cursor.fetchall()
        
        return [booking[0] for booking in bookings]
    
    except Exception as error:
        print(f'Error occurred while fetching booking IDs: {error}')
        return []
    
    finally:
        cursor.close()
        connection.close()
        

#WHY ISNT THE FEE BEING BOOKED 
# caches fee into fee collection
def cache_fees(booking_id, fee_type, fee):
    try:
        #print(f'FEE_TYPE: {fee_type}')
        #print(f'FEE: {fee}')
        #print(f'BOOKING_ID: {booking_id}')
        fee = float(fee)
        
        cost = {
            "booking_id": booking_id,
            "fee_type": fee_type, 
            "fee": fee
        }
        
        dbcollection_fee.insert_one(cost)
        print("Successfully inserted fee")
        
    except Exception as error: 
        print(f'Error occured while storing fee: {error}')
        
# caching booking status
def cache_booking_status(book_id, status):
    try:
        status = {
            "booking_id": book_id, 
            "status": status
        }
       
        dbcollection_booking_status.insert_one(status)
        print("cached room status")
    except Exception as error:
        print(f'Error occured while caching satus: {error}')
    
# approving the booking as a Manager user
# Manager approve or reject bookings


def approve_booking(user): 
    if user['role'] != 'Manager':
        print("Access denied")
        return
        
    try: 
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        booking_id = int(input("Please enter booking ID to Approve/Reject: "))
        status = input("Please enter status (Approved/Rejected): ")
        
        # Update booking status in MySQL
        update_status_query = """
            UPDATE Bookings
            SET status = %s
            WHERE booking_id = %s
        """
        cursor.execute(update_status_query, (status, booking_id))
        
        # Insert into CheckInCheckOut table
        insert_query = """
            INSERT INTO CheckInCheckOut (booking_id, check_in_time, check_out_time)
            VALUES (%s, NULL, NULL)
        """
        cursor.execute(insert_query, (booking_id,))
        
        # Retrieve user_id, start_date, and end_date from Bookings
        retrieve_details_query = """
            SELECT user_id, start_date, end_date
            FROM Bookings
            WHERE booking_id = %s
        """
        cursor.execute(retrieve_details_query, (booking_id,))
        booking_details = cursor.fetchone()  # Fetch the result

        if booking_details:
            #user_id, start_date, end_date = booking_details
            
            # Update booking status in MongoDB
            update_booking_status_in_mongo(booking_id)
            
            # Cache the status into MongoDB
            cache_booking_status(booking_id, status)
            
            print('Successfully Updated Booking')
        else:
            print("Booking details not found.")
        
        connection.commit()
        
    except Exception as error:
        print(f'Error occurred while approving booking: {error}')
    finally: 
        cursor.close()
        connection.close()


# Display all booking information for staff
def display_bookings_for_manager(): 
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Display all details for Manager
        query_select = """
            SELECT * 
            FROM Bookings
        """
        cursor.execute(query_select)
        result = cursor.fetchall()
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        if result:
            # Print column names with fixed width
            column_widths = [max(len(name), 12) for name in column_names]  # Dynamic column widths based on header length
            format_str = " ".join(["{:<" + str(width) + "}" for width in column_widths])
            print(format_str.format(*column_names))
            print("-" * sum(column_widths))  # Add a separator line for better readability
            
            # Print each row of results with fixed width
            for row in result:
                row = [str(item) if not isinstance(item, datetime) else item.strftime("%Y-%m-%d") for item in row]
                print(format_str.format(*row))
        else:
            print("No data found")
    except Exception as error: 
        print(f'Error occurred while fetching data from SQL: {error}')
    finally: 
        cursor.close()
        connection.close()
        

#Upadtes the status of a booking from pending to approved 
def update_booking_status_in_mongo(booking_id):
    try:
        # Update the booking status in MongoDB
        dbcollection_room_booking.update_one(
            {"booking_id": booking_id}, 
            {"$set": {"status": "Approved"}}
        )
        print('Successfully updated booking')
        
    except Exception as error:
        print(f'Error occurred while updating booking status in MongoDB: {error}')


# Staff check-in - staff memebers can change the status of user checkin 
def check_in(user): 
    if user['role'] != 'Staff': 
        print("Access denied")
        return
    
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # display all data stored in checking sql 
        show_checking_data()
        
        # get the booking id
        booking_id = int(input("Please enter booking id: "))
        check_in_time = datetime.now() 
        print(f'CHECK IN TIME: {check_in_time}')

        
      # Update the check-in time in the CheckInCheckOut table
        update_query_checkin = """
            UPDATE CheckInCheckOut
            SET check_in_time = %s
            WHERE booking_id = %s
        """
        cursor.execute(update_query_checkin, (check_in_time, booking_id))
        
        connection.commit()
        cache_check_in_time(booking_id, check_in_time)
        print("Check-in time updated successfully.")
        
    except Exception as error: 
        print(f'Error while checking in: {error}')
        connection.rollback()
    
    finally: 
        cursor.close()
        connection.close()
    

# Staff updates the checkout
def check_out(user): 
    if user['role'] != 'Staff': 
        print('Access denied')

    try: 
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # display all data stored in checking sql 
        show_checking_data()
        
        booking_id = int(input("Please enter booking id: "))
        check_out_time = datetime.now()
        print(f'CHECK OUT TIME: {check_out_time}')

        # qurey to update check out time 
        update_query_checkout = """
            UPDATE CheckInCheckOut
            SET check_out_time = %s
            WHERE booking_id = %s
        """
        cursor.execute(update_query_checkout, (check_out_time, booking_id))
        connection.commit()
        
        cursor.execute("SELECT * FROM CheckInCheckOut WHERE booking_id = %s", (booking_id,))
        result = cursor.fetchone()
        print(f"Updated CheckInCheckOut Record: {result}")
        
        
        update_checkin_status(booking_id, check_out_time)
        
        #Fetch the room type from the Bookings table
        select_query_booking = """
            SELECT room_type
            FROM Bookings
            WHERE booking_id = %s
        """
        cursor.execute(select_query_booking, (booking_id,))
        result = cursor.fetchone()
        
        if result:
            room_type = result[0]
            
            # Update room availability
        update_room_availability(room_type, 1)
    
    except Exception as error: 
        print(f'Error while checking out: {error}')
    
    finally: 
        connection.close()
        cursor.close()
        

def insert_checkin_checkout(booking_id):
    try:
        # Establish a database connection
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Define the SQL query to insert a new record with check-in and check-out times as NULL
        query_insert = """
            INSERT INTO CheckInCheckOut (booking_id, check_in_time, check_out_time)
            VALUES (%s, NULL, NULL)
        """
        
        # Execute the query with the given booking_id
        cursor.execute(query_insert, (booking_id,))
        
        # Commit the transaction
        connection.commit()
        print("CheckInCheckOut record inserted successfully.")
    
    except Exception as error:
        print(f'Error occurred while inserting into CheckInCheckOut: {error}')
        connection.rollback()
    
    finally:
        # Close the cursor and connection
        cursor.close()
        connection.close()
        
        
def update_checkin_status(booking_id, check_out_time): 
    try:
        result = dbcollection_check_in_and_check_out.update_one(
            {"booking_id": booking_id}, 
            {"$set": {"status": "check_out", "check_out_time": check_out_time}}
        )
        if result.modified_count > 0:
            print(f"Check-out status updated in MongoDB for booking ID {booking_id}")
        else:
            print(f"No document found in MongoDB for booking ID {booking_id}")
    except Exception as error: 
        print(f'Error occurred while updating check-out time in MongoDB: {error}')
    
    
def cache_check_in_time(booking_id, check_in_time): 
    try:
        
        check_in_time = {
            "booking_id": booking_id, 
            "check_in_time": check_in_time, 
            "check_out_time": None, 
            "status": "check_in"
        }
        
        dbcollection_check_in_and_check_out.insert_one(check_in_time)
        print("Check-in successful")
        
    except Exception as error: 
        print(f'Error while caching check in time {error}')
    
#Display the room service details
def display_room_service(): 
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        query_select = """
            SELECT * 
            FROM Services
        """
        
        cursor.execute(query_select)
        result = cursor.fetchall()
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        if result: 
            # Print column names with fixed width
            print("{:<12} {:<12} {:<15} {:<10} {:<10}".format(*column_names))
            print("-" * 64)  # Add a separator line for better readability

            # Print each row of results with fixed width
            for row in result: 
                print("{:<12} {:<12} {:<15} {:<10} {:<10}".format(*row))
        else: 
            print("No data found")
        
    except Exception as error: 
        print(f'Error occurred while getting Services: {error}')
    
    finally: 
        cursor.close()
        connection.close()

#CUSTOMER - customer make a service request to Staff members to filfull
#stores room service based on customer input into mongo
def room_service(user):
    if user['role'] != 'Customer':
        print("Access denied for room service")
        return

    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()

        room_service = input("Please Enter a room service (Cleaning, Food, Laundry): ")

        query_select = """
            SELECT fee
            FROM PredefinedServices
            WHERE service_type = %s
        """

        cursor.execute(query_select, (room_service,))
        result = cursor.fetchone()

        if not result:
            print("Invalid service type")
            return

        fee = float(result[0])

        book_id_query = """
            SELECT booking_id FROM Bookings
            WHERE user_id = (SELECT user_id FROM Users WHERE username = %s)
            AND status = 'Approved'
            ORDER BY start_date DESC
            LIMIT 1
        """

        cursor.execute(book_id_query, (user['username'],))
        booking = cursor.fetchone()

        if not booking:
            print("No active booking found for the user")
            return

        booking_id = int(booking[0])

        # Store service into SQL
        insert_query = """
            INSERT INTO Services (booking_id, service_type, fee, status)
            VALUES (%s, %s, %s, 'Requested')
        """

        cursor.execute(insert_query, (booking_id, room_service, fee))

        # Get the inserted service_id
        cursor.execute("SELECT LAST_INSERT_ID()")
        service_id = cursor.fetchone()[0]
        
        connection.commit()


        # Cache service request
        cache_service_request(service_id, booking_id, room_service, fee)
        
        # cache the room service fee into fees 
        cache_fees(booking_id, "service_fee" ,fee )
        
        #Insert data into Fees tables 
        insert_into_fee("service_fee", fee)
        
    except Exception as error:
        print(f'Error occurred during room service: {error}')
        if "Lock wait timeout" in str(error):
            print("Transaction is taking too long. Please try again later.")

    finally:
        cursor.close()
        connection.close()

#Insert data into fees
def insert_into_fee(fee_type, fee): 
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        insert_query = """
            INSERT INTO Fees(fee_type, fee)
            VALUES(%s, %s)
        """
        
        cursor.execute(insert_query, (fee_type, fee,))
        connection.commit()
        print("Sucessfully inserted Fees table")
    
    except Exception as error: 
        print( f'Error occured while inserting into fees: {error}')
    

#NOT THE BEST CODE BUT IT WORKS
def cache_service_request(service_id, booking_id, room_service, fee):
    try:
        service_request = {
            "service_id": service_id,
            "booking_id": booking_id,
            "room_service": room_service,
            "fee": fee,
            "status": "Requested",
            "request_time": datetime.now()
        }

        dbcollection_service_request.insert_one(service_request)
        print("Service request cached into Mongo")
        return service_id

    except Exception as error:
        print(f'Error occurred while caching service request: {error}')
        return None


#fulfill a service request
def all_service_request_fulfilled():
    try: 
        
        #Get all service id and status from cached mongo collection
        service_request = dbcollection_service_request.find({}, {"Service_id": 1, "status": 1})
        
        # store all non completed service request into a variable 
        incomplete_requests = [sr for sr in service_request if sr['status'] != 'Completed']
        
        if not incomplete_requests:
            print("All service requests have been completed.")
        else:
            print("The following service requests have not been completed:")
            for request in incomplete_requests:
                print(f"Service ID: {request['service_id']}, Status: {request['status']}")
            print("Please complete these requests.")
            
        
            
    except Exception as error: 
        print(f'Error occured while checking service request: {error}')
    
# STAFF - staff fulfill customer service request
def fulfill_room_service(user): 
    if user['role'] != 'Staff': 
        print("Access deined")
        return
    
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        service_request = dbcollection_service_request.find({}, {"Service_id": 1, "status": 1})
        
        # store all non completed service request into a variable 
        incomplete_requests = [sr for sr in service_request if sr['status'] != 'Completed']
        
        if not incomplete_requests:
            print("All service requests have been completed.")
        else: 
            # display all room services
            display_room_service()
            
            
            service_id = int(input("Enter Service id to fulfill: "))
            
            #qurey to update the status of a room request
            update_query = """
                UPDATE Services
                SET status = 'Completed'
                WHERE service_id = %s
            """
            
            #execute the update qurey based on service id 
            cursor.execute(update_query, (service_id,))
            connection.commit()
            
            # update the cached data in mongo to the new status
            update_cache_service_request(service_id, 'Completed')
          
        
    except Exception as error: 
        print(f'Error occured wqhile fulfilling room serivce: {error}')
    
    finally: 
        connection.close()
        cursor.close()
        
#MONITOR CODE 
#Updates the service request made from pending to completed
def update_cache_service_request(service_id, status): 
    try:
        result = dbcollection_service_request.update_one(
            {"service_id": service_id}, 
            {"$set": {"status": status}}
        )
        
        if result.matched_count == 0:
            print(f"No document found with service_id {service_id}.")
        elif result.modified_count == 0:
            print(f"Document with service_id {service_id} was not updated.")
        else:
            print("Service status updated in MongoDB.")
    
    except Exception as error: 
        print(f"Error occurred while caching updated room service: {error}")
        

# Check if there any booking needsd to be approved or not
def check_booking_status():
    try:
        # Connect to MySQL
        connection = get_mysql_connection()
        cursor = connection.cursor()

        # Query to check for any pending bookings
        query = """
            SELECT COUNT(*) 
            FROM Bookings 
            WHERE status != 'Approved'
        """
        cursor.execute(query)
        result = cursor.fetchone()
        pending_count = result[0]

        # Return True if there are pending bookings, False otherwise
        return pending_count > 0

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False  # Return False if there's an error
    
    finally:
        cursor.close()
        connection.close()


# Display checking data check in and checkout 
def show_checking_data():
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Query to select all details from CheckInCheckOut table
        query_select = """
            SELECT * 
            FROM CheckInCheckOut
        """
        cursor.execute(query_select)
        result = cursor.fetchall()
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        if result:
            # Print column names with fixed width
            print("{:<12} {:<12} {:<20} {:<20}".format(*column_names))
            print("-" * 64)  # Add a separator line for better readability
            
            # Print each row of results with fixed width
            for row in result:
                record_id, booking_id, check_in_time, check_out_time = row
                
                # Handle None values for check_in_time and check_out_time
                check_in_time_str = check_in_time.strftime("%Y-%m-%d %H:%M:%S") if check_in_time else 'N/A'
                check_out_time_str = check_out_time.strftime("%Y-%m-%d %H:%M:%S") if check_out_time else 'N/A'
                
                print("{:<12} {:<12} {:<20} {:<20}".format(
                    record_id, booking_id, check_in_time_str, check_out_time_str
                ))
        else:
            print("No data found")
    except Exception as error: 
        print(f'Error occurred while fetching data from SQL: {error}')
    finally: 
        cursor.close()
        connection.close()
    
            
#ADIM - displays all the data for admin, to either update, delete 
#or add new user 
def display_users():
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        select_qurey = """
            SELECT * 
            FROM Users
        """
        
        cursor.execute(select_qurey)
        users = cursor.fetchall()
                
        column_names = [desc[0] for desc in cursor.description]

        if users:
            # Print column names with fixed width
            print("\n{:<8} {:<10} {:<10} {:<10}".format(*column_names))
            print("-" * 38)  # Add a separator line for better readability
            
            # Print each row of results with fixed width
            for row in users:
                user_id, username, password, role = row
                print("{:<8} {:<10} {:<10} {:<10}".format(
                    user_id, username, password, role
                ))
        else:
            print("No users found")
    except Exception as error: 
        print(f'Error occured while displaying all users: {error}')
    finally: 
        connection.close()
        cursor.close()


#ADMIN- Creating new user based on input 
def create_new_user(): 
    try: 
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        display_users()
        
        user_name = input("Enter username: ")
        password = input("Enter password: ")
        role = input("Please enter a role (Customer, Staff, Manager): ")
        
        valid_roles = ['Customer', 'Staff', 'Manager']
        
        #CREATE LOOP - make this code better
        if role not in valid_roles:
            print("Invalid role. Please enter one of the following: Customer, Staff, Manager")
            return
        
        insert_query = """
            INSERT INTO Users (username, password, role) 
            VALUES (%s, %s, %s)
        """
        
        cursor.execute(insert_query, (user_name, password, role,))
        connection.commit()
        
        print("Successfully created new user")
        display_users()

    except Exception as error: 
        print(f'Error occured while creating new user: {error}')
    
    finally: 
        cursor.close()
        connection.close()

#Admin Updating user
def update_user(): 
    try: 

        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        display_users()
        print("Please enter the id of the user to update\n")
        
        user_id = int(input("Enter user id: "))

        user_name = input("Enter username: ")
        password = input("Enter password: ")
        role = input("Please enter a role (Customer, Staff, Manager): ")
        
        valid_roles = ['Customer', 'Staff', 'Manager']
        
        if role not in valid_roles:
            print("Invalid role. Please enter one of the following: Customer, Staff, Manager")
            return
        
        update_query = """
            UPDATE Users
            SET username = %s, password = %s, role = %s
            WHERE user_id = %s
        """
        
        cursor.execute(update_query, (user_name, password, role, user_id,))
        connection.commit()
        
        print("Successfully updated user")
        display_users()
        
    except Exception as error: 
        print(f'Error occured while updating user: {error}')
    
    finally: 
        cursor.close()
        connection.close()
        
    
#Admin deleteing a user
def delete_user(): 
    try: 
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        display_users()
        print("Please enter the id of the user to Delete\n")
        
        user_id = int(input("Enter user id: "))
        
        delete_query = """
            DELETE
            FROM Users
            WHERE user_id = %s
        """
        
        cursor.execute(delete_query, (user_id,))
        connection.commit()
        
        print("Successfully Deleted user")
        display_users()
        
    except Exception as error: 
        print(f'Error occured while deleting user: {error}')
    
    finally: 
        cursor.close()
        connection.close()
        
    
# MYBE FIX IF ISSES ARRISE 
def check_all_room_availability():
    try:
        connection = get_mysql_connection()
        cursor = connection.cursor()

        # Query to fetch all room types and their available rooms
        check_availability_query = """
            SELECT room_type, available_rooms 
            FROM RoomAvailability
        """
        cursor.execute(check_availability_query)
        results = cursor.fetchall()

        if not results:
            print("No room types found.")
            return

        print("\nRoom Availability:")
        print("-"*50)
        for row in results:
            room_type, available_rooms = row
            print(f"Room type: {room_type}, Available rooms: {available_rooms}")

    except Exception as error:
        print(f"Error while checking room availability: {error}")
    
    finally:
        cursor.close()
        connection.close()
        

#Updates the room availibity - takes room type to update and the change is the icnreament or decrement 
def update_room_availability(room_type, change):
    try:
        #connect to my sql 
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        query = "UPDATE RoomAvailability SET available_rooms = available_rooms + %s WHERE room_type = %s"
        cursor.execute(query, (change, room_type))
        
        connection.commit()
    except Exception as error:
        print(f'Error occurred while updating room availability: {error}')
    finally:
        cursor.close()
        connection.close()
        

#FIX THE FEES 
# Generete a report for the admin
def generate_financial_report():
    try:
        # Get distinct booking IDs
        booking_ids = dbcollection_fee.distinct('booking_id')

        for booking_id in booking_ids:
            # Calculate total booking fee
            total_booking_fee = dbcollection_fee.aggregate([
                {
                    '$match': {
                        'booking_id': booking_id,
                        'fee_type': 'booking_fee'
                    }
                },
                {
                    '$group': {
                        '_id': None,
                        'total_booking_fee': {
                            '$sum': '$fee'
                        }
                    }
                }
            ])
            
            # Calculate total service fee
             # Calculate total service fee from ServiceRequests
            total_service_fee = dbcollection_service_request.aggregate([
                {
                    '$match': {
                        'booking_id': booking_id
                    }
                },
                {
                    '$group': {
                        '_id': None,
                        'total_service_fee': {
                            '$sum': '$fee'
                        }
                    }
                }
            ])

            # Fetch the results
            total_booking_fee = next(total_booking_fee, {'total_booking_fee': 0})['total_booking_fee']
            total_service_fee = next(total_service_fee, {'total_service_fee': 0})['total_service_fee']

            # Calculate grand total
            grand_total = total_booking_fee + total_service_fee

            # Print the results
            print(f"\nBooking ID: {booking_id}")
            print(f"Total Booking Fee: ${total_booking_fee:.2f}")
            print(f"Total Service Fee: ${total_service_fee:.2f}")
            print(f"Grand Total: ${grand_total:.2f}")
            print("----------------------------")

    except Exception as error:
        print(f"Error occurred while calculating total fees: {error}")
        

# Checks if there is any check in or check out data that need to be taken care of 
def check_null_dates():
    try:
        # Connect to MySQL
        connection = get_mysql_connection()
        cursor = connection.cursor()

        # Query to check for null values in start_date or end_date
        query = """
            SELECT COUNT(*)
            FROM Bookings
            WHERE start_date IS NULL OR end_date IS NULL
        """
        cursor.execute(query)
        result = cursor.fetchone()
        null_count = result[0]

        # Return True if there are null values, False otherwise
        return null_count > 0

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False  # Return False if there's an error
    
    finally:
        cursor.close()
        connection.close()
        

def display_options(): 
    print("\n1. Home")
    print("2. About Us")
    print("3. Room Booking")
    print("4. Check-In/Check-Out")
    print("5. Room Service")
    print("6. Fees and Rules")
    print("7. Contact Us")
    print("8. Exit")


def about_us(): 
    print("Optimus Prime (Owner): The visionary leader ensuring the highest standards of hospitality and guest satisfaction.")
    print("Bumblebee (General Manager): Overseeing daily operations and ensuring seamless guest experiences")
    print("Ratchet (Head of Maintenance): Maintaining the hotel's state-of-the-art facilities and ensuring everything runs smoothly")
    print("Arcee (Head of Guest Relations): Ensuring all guests have a memorable and enjoyable stay.\n")
    
    
def contact_us(): 
    print("Email: Hotel.Management@hotmail.ca")
    print("Phone: 604-999-9999")
    

def manager_display(): 
    print("\n1. Update bookong status")
    print("2. Show Daily Activity")
    print("3. return to login\n")


def staff_display(): 
    print("\nPlease one the two options")
    print("1. Check-in")
    print("2. Check-out")
    print("3. Display Check In and Check Out")
    print("4. exit")


def login_display():
    print("\n1. Register")
    print("2. Login")
    print("3. exit")
    

def display_admin_information(): 
    print("\n1. Create new user")
    print("2. Update user")
    print("3. Delete user")
    print("4. Display financial Report")
    print("5. Exit")



def fees(): 
    try: 
        connection = get_mysql_connection()
        cursor = connection.cursor()
        
        # Fetch predefined services fees
        select_query_predefinedservices = """
            SELECT * FROM PredefinedServices
        """
        cursor.execute(select_query_predefinedservices)
        pred_fees = cursor.fetchall()
        
        # Print PredefinedServices table
        print("Predefined Services Fees:")
        print(f"+{'-'*12}+{'-'*14}+{'-'*7}+")
        print(f"| {'service_id':<10} | {'service_type':<12} | {'fee':<5} |")
        print(f"+{'-'*12}+{'-'*14}+{'-'*7}+")
        for row in pred_fees:
            print(f"| {row[0]:<10} | {row[1]:<12} | {row[2]:<5.2f} |")
        print(f"+{'-'*12}+{'-'*14}+{'-'*7}+")
        
        # Fetch room fees
        select_query_room_fees = """
            SELECT * FROM RoomFees
        """
        cursor.execute(select_query_room_fees)
        room_fees = cursor.fetchall()
        
        # Print RoomFees table
        print("\nRoom Fees:")
        print(f"+{'-'*12}+{'-'*7}+")
        print(f"| {'room_type':<10} | {'fee':<5} |")
        print(f"+{'-'*12}+{'-'*7}+")
        for row in room_fees:
            print(f"| {row[0]:<10} | {row[1]:<5.2f} |")
        print(f"+{'-'*12}+{'-'*7}+")
        
        # Fetch room service fees
        select_query_room_service_fees = """
            SELECT booking_id, service_type, fee
            FROM RoomServiceFees
        """
        cursor.execute(select_query_room_service_fees)
        room_service_fees = cursor.fetchall()
        
        # Print RoomServiceFees table
        print("\nRoom Service Fees:")
        print(f"+{'-'*12}+{'-'*12}+{'-'*7}+")
        print(f"| {'booking_id':<10} | {'service_type':<12} | {'fee':<5} |")
        print(f"+{'-'*12}+{'-'*12}+{'-'*7}+")
        for row in room_service_fees:
            print(f"| {row[0]:<10} | {row[1]:<12} | {row[2]:<5.2f} |")
        print(f"+{'-'*12}+{'-'*12}+{'-'*7}+")
        
    except Exception as error: 
        print(f'Error occurred while getting fees: {error}')
    
    finally:
        cursor.close()
        connection.close()

#Displays all the Pending or completed serivce request by the user
#shows fee and type of service
def display_all_service_requests_by_booking_id(booking_id):
    try:
        # Define a pipeline to match all room service requests by the booking ID
        pipeline = [
            {"$match": {"booking_id": booking_id}},
            {"$project": {"_id": 0, "room_service": 1, "request_time": 1, "status": 1, "fee": 1}}
        ]
        
        # Query the MongoDB collection
        all_services = list(dbcollection_service_request.aggregate(pipeline))
        
        if not all_services:
            print(f"No room service requests found for booking ID {booking_id}.")
            return
        
        # Display all room service requests
        print(f"\nAll Room Service Requests for Booking ID {booking_id}:")
        print(f"+{'-'*15}+{'-'*25}+{'-'*10}+{'-'*10}+")
        print(f"| {'Service Type':<14} | {'Request Time':<24} | {'Status':<9} | {'Fee':<9} |")
        print(f"+{'-'*15}+{'-'*25}+{'-'*10}+{'-'*10}+")
        
        for service in all_services:
            request_time = service['request_time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(service['request_time'], datetime) else str(service['request_time'])
            print(f"| {service['room_service']:<14} | {request_time:<24} | {service['status']:<9} | {service['fee']:<9.2f} |")
        
        print(f"+{'-'*15}+{'-'*25}+{'-'*10}+{'-'*10}+")
    
    except Exception as error:
        print(f'Error occurred while displaying room service requests: {error}')


#Display the total cost when current user logs out, this inculde 
#booking fee and service fee and grand total cost
def display_total_fees(booking_id):
    try:
        # Calculate the total booking cost
        total_booking_cost_cursor = dbcollection_fee.aggregate([
            {"$match": {"booking_id": booking_id, "fee_type": "booking_fee"}},
            {"$group": {"_id": None, "total_booking_cost": {"$sum": "$fee"}}}
        ])
        
        total_booking_cost_result = list(total_booking_cost_cursor)
        total_booking_cost = total_booking_cost_result[0]["total_booking_cost"] if total_booking_cost_result else 0
        
        # Calculate the total room service cost
        total_room_service_cost_cursor = dbcollection_fee.aggregate([
            {"$match": {"booking_id": booking_id, "fee_type": "service_fee"}},
            {"$group": {"_id": None, "total_room_service_cost": {"$sum": "$fee"}}}
        ])
        
        total_room_service_cost_result = list(total_room_service_cost_cursor)
        total_room_service_cost = total_room_service_cost_result[0]["total_room_service_cost"] if total_room_service_cost_result else 0
        
        # Display the total costs
        grand_total = total_booking_cost + total_room_service_cost
        print(f"\nBooking ID: {booking_id}")
        print(f"+{'-'*19}+{'-'*19}+{'-'*12}+")
        print(f"| {'Total Booking Cost':<18} | {'Total Room Service Cost':<18} | {'Grand Total':<11} |")
        print(f"+{'-'*19}+{'-'*19}+{'-'*12}+")
        print(f"| ${total_booking_cost:<17.2f} | ${total_room_service_cost:<17.2f} | ${grand_total:<10.2f} |")
        print(f"+{'-'*19}+{'-'*19}+{'-'*12}+")
    
    except Exception as error:
        print(f'Error occurred while displaying total fees: {error}')


#Returns the booking id based on user username
#index to get booking id
def get_booking_id(username): 
    booking_ids = get_current_user_booking_ids(username)
    if booking_ids:
        return booking_ids[0]
    else:
        return None

#displays customer booking status and check in and checkouts
def display_booking_details(user_id):
    try:
        # Fetch the booking details from MongoDB
        booking = dbcollection_room_booking.find_one({"user_id": user_id})
        
        if booking:
            print("Booking Details:")
            print(f"+{'-'*12}+{'-'*12}+{'-'*10}+")
            print(f"| {'Start Date':<11} | {'End Date':<11} | {'Status':<9} |")
            print(f"+{'-'*12}+{'-'*12}+{'-'*10}+")
            print(f"| {booking.get('start_date', 'N/A'):<11} | {booking.get('end_date', 'N/A'):<11} | {booking.get('status', 'N/A'):<9} |")
            print(f"+{'-'*12}+{'-'*12}+{'-'*10}+")
        else:
            print("No booking found for the given user ID.")
    
    except Exception as error:
        print(f'Error occurred while displaying booking details: {error}')


def main():
    setup_database()
    user = None

    while not user:
        # Display login or register option
        login_display()

        try:
            user_choice = int(input("Enter your choice: "))
        except ValueError:
            print("Invalid input. Please enter a number.")
            continue

        if user_choice == 1: 
            # Register user and store data into SQL
            register()
        elif user_choice == 2: 
            # Retrieve user data and login
            user = login()
        elif user_choice == 3:
            # Exit the program
            return
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
            continue
        
        while user:
            try:
                if user['role'] == 'Customer': 
                    # Display options in the main page
                    display_options()
                    user_choice = int(input("\nPlease choose an option: "))
                    
                    if user_choice == 1:
                        break
                    
                    elif user_choice == 2:
                        # About us
                        about_us()
                        
                    elif user_choice == 3: 
                        # Book room - Customer
                        check_all_room_availability()
                        book_room(user)
                        
                    elif user_choice == 4: 
                        # Display booking details and service requests
                        display_booking_details(user['user_id'])
                        booking_id = get_booking_id(user['username'])
                        display_all_service_requests_by_booking_id(booking_id)
                    
                    elif user_choice == 5:
                        # Room Service - Customer
                        room_service(user)
                        
                    elif user_choice == 6: 
                        fees()
                        
                    elif user_choice == 7: 
                        contact_us()
                        
                    elif user_choice == 8: 
                        # Get booking ID to display total cost
                        booking_id = get_booking_id(user['username'])
                        display_total_fees(booking_id)
                        return  # Exit the program
                        
                    else:
                        print("Invalid choice. Please enter a valid option.")
                
                elif user['role'] == 'Manager': 
                    while True:
                        manager_display()
                        user_choice = int(input("Please enter choice: "))
                        
                        if user_choice == 1:
                            # Approving booking
                            
                            # Check for any bookings that need approving or rejecting
                            if check_booking_status():
                                print("There are pending room bookings.")
                            else:
                                print("All room bookings are approved.")
                                break
                    
                            display_bookings_for_manager()
                            approve_booking(user)
                        elif user_choice == 2:
                            # Generating monthly report
                            generate_daily_activity_report(datetime.now())
                        elif user_choice == 3: 
                            return  # Exit the program
                        else: 
                            print("Invalid choice. Please enter a valid option.")
                         
                elif user['role'] == 'Staff': 
                    exit_flag = False
                    while not exit_flag:
                        display_options()
                        user_choice = int(input("Please choose an option: "))
                        
                        if user_choice == 4: 
                            staff_display()
                            user_choice = int(input("Please choose an option: "))
                            
                            if user_choice == 1:
                                #if check_null_dates():
                                    #print("There are bookings with null start_date or end_date.")
                                check_in(user)
                                #else:
                                    #print("All bookings have valid start_date and end_date.")
                                    #break; 
                            elif user_choice == 2:
                                
                                #if check_null_dates():
                                    #print("There are bookings with null start_date or end_date.")
                                check_out(user)
                                #else:
                                    #print("All bookings have valid start_date and end_date.")
                                    #break;
                               
                            elif user_choice == 3: 
                                # Display all check-ins and check-outs
                                show_checking_data()
                            elif user_choice == 4: 
                                exit_flag = True
                            elif user_choice == 8: 
                                return  # Exit the program
                            else: 
                                print("Please enter a valid choice")
                        elif user_choice == 5: 
                            # Check if all service requests have been fulfilled
                            fulfill_room_service(user)
                        elif user_choice == 2: 
                            about_us()
                        elif user_choice == 3: 
                            print("Access denied")
                        elif user_choice == 6: 
                            fees()
                        elif user_choice == 7: 
                            contact_us()
                        elif user_choice == 8:
                            return  # Exit the program
                        else: 
                            print("Please enter a valid choice")
                    
                elif user['role'] == 'Admin': 
                    while True:
                        display_admin_information()
                        user_choice = int(input("Please enter a choice: "))
                        
                        if user_choice == 1:
                            create_new_user()
                        elif user_choice == 2:
                            update_user()
                        elif user_choice == 3:
                            delete_user()
                        elif user_choice == 4:
                            generate_financial_report()
                        elif user_choice == 5:
                            return  # Exit the program
                        else:
                            print("Invalid choice. Please enter a valid option.")
                else:
                    print("Unknown user role.")
                    break

            except ValueError:
                print("Invalid input. Please enter a number.")
            except Exception as e:
                print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()