from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
import pymysql.cursors
from datetime import datetime
import math

app = Flask(__name__)
app.secret_key = 'bubbleflow_secret_key'

# --- Database Configuration ---
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',      # Default XAMPP/WAMP user
        password='',      # Default password is empty
        database='laundry_db',
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').lower()
        password = request.form.get('password')

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # Query to find user
                sql = "SELECT * FROM users WHERE email=%s AND password=%s"
                cursor.execute(sql, (email, password))
                user = cursor.fetchone()

                if user:
                    # Store user info in session
                    session['user'] = {
                        'user_id': user['user_id'],
                        'name': user['name'],
                        'email': user['email'],
                        'role': user['role']
                    }
                    flash(f"Welcome back, {user['name']}!", "success")
                    return redirect(url_for('admin_dashboard' if user['role'] == 'admin' else 'user_dashboard'))
                else:
                    flash("Invalid email or password.", "error")
        finally:
            connection.close()

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email').lower()
        password = request.form.get('password')
        role = request.form.get('role')

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # Check if email exists
                cursor.execute("SELECT user_id FROM users WHERE email=%s", (email,))
                if cursor.fetchone():
                    flash("Email already exists!", "error")
                    return redirect(url_for('register'))

                # Insert new user
                sql = "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (name, email, password, role))
                connection.commit()
                
                flash("Registration successful! Please login.", "success")
                return redirect(url_for('login'))
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "error")
        finally:
            connection.close()

    return render_template('register.html')

@app.route('/user_dashboard')
def user_dashboard():
    if 'user' not in session or session['user']['role'] != 'user':
        return redirect(url_for('login'))
    
    user_id = session['user']['user_id']
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Get active services
            cursor.execute("SELECT * FROM services WHERE status='active'")
            services = cursor.fetchall()
            
            # Add descriptions
            for service in services:
                if service['service_name'] == 'Wash':
                    service['description'] = 'Standard washing with detergent'
                elif service['service_name'] == 'Dry':
                    service['description'] = 'Machine drying'
                elif service['service_name'] == 'Fold':
                    service['description'] = 'Professional folding'
                elif service['service_name'] == 'Iron':
                    service['description'] = 'Ironing and steaming'
                else:
                    service['description'] = 'Premium service'
            
            # Get order stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_orders
                FROM orders 
                WHERE user_id=%s
            """, (user_id,))
            stats = cursor.fetchone()
            
            # Get recent orders (last 3)
            cursor.execute("""
                SELECT o.*, 
                       GROUP_CONCAT(s.service_name) as service_names
                FROM orders o
                LEFT JOIN order_services os ON o.order_id = os.order_id
                LEFT JOIN services s ON os.service_id = s.service_id
                WHERE o.user_id=%s
                GROUP BY o.order_id
                ORDER BY o.created_at DESC
                LIMIT 3
            """, (user_id,))
            recent_orders = cursor.fetchall()
            
    finally:
        connection.close()
    
    return render_template('user_dashboard.html',
                         services=services,
                         total_orders=stats['total_orders'] if stats else 0,
                         completed_orders=stats['completed_orders'] if stats else 0,
                         recent_orders=recent_orders)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user' not in session or session['user']['role'] != 'user':
        return redirect(url_for('login'))
    
    user_id = session['user']['user_id']
    
    if request.method == 'POST':
        # Handle form submission
        new_name = request.form.get('name')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # Get current user data
                cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
                user = cursor.fetchone()
                
                # Verify current password if trying to change password
                if current_password or new_password:
                    if user['password'] != current_password:
                        flash("Current password is incorrect.", "error")
                        return redirect(url_for('edit_profile'))
                    
                    if new_password != confirm_password:
                        flash("New passwords do not match.", "error")
                        return redirect(url_for('edit_profile'))
                    
                    if len(new_password) < 6:
                        flash("Password must be at least 6 characters.", "error")
                        return redirect(url_for('edit_profile'))
                
                # Update user information
                update_fields = []
                update_values = []
                
                if new_name and new_name != user['name']:
                    update_fields.append("name = %s")
                    update_values.append(new_name)
                
                if new_password and new_password != user['password']:
                    update_fields.append("password = %s")
                    update_values.append(new_password)
                
                if update_fields:
                    update_values.append(user_id)
                    sql = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = %s"
                    cursor.execute(sql, update_values)
                    connection.commit()
                    
                    # Update session
                    session['user']['name'] = new_name if new_name else session['user']['name']
                    
                    flash("Profile updated successfully!", "success")
                else:
                    flash("No changes were made.", "info")
                    
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "error")
        finally:
            connection.close()
        
        return redirect(url_for('edit_profile'))
    
    # GET request - display form
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Get user stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending_orders,
                    SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_orders
                FROM orders 
                WHERE user_id=%s
            """, (user_id,))
            user_stats = cursor.fetchone()
            
            # Get the user's first order date to approximate member since
            cursor.execute("""
                SELECT MIN(created_at) as first_order_date 
                FROM orders 
                WHERE user_id=%s
            """, (user_id,))
            first_order = cursor.fetchone()
            
            # Get user details
            cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
            user_data = cursor.fetchone()
            
    finally:
        connection.close()
    
    # Create a user dictionary with additional data for the template
    user_info = {
        'name': user_data['name'],
        'email': user_data['email'],
        'role': user_data['role'],
        'created_at': first_order['first_order_date'] if first_order and first_order['first_order_date'] else datetime.now()
    }
    
    return render_template('edit_profile.html', 
                         user_stats=user_stats,
                         user=user_info)

@app.route('/submit_order', methods=['POST'])
def submit_order():
    if 'user' not in session or session['user']['role'] != 'user':
        return redirect(url_for('login'))
    
    weight = float(request.form.get('weight'))
    service_ids = request.form.getlist('services')
    
    if not service_ids:
        flash("Please select at least one service.", "error")
        return redirect(url_for('user_dashboard'))
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Calculate total cost
            total = 0
            cursor.execute("SELECT * FROM services WHERE service_id IN (%s)" % 
                         ','.join(['%s']*len(service_ids)), service_ids)
            services = cursor.fetchall()
            
            for service in services:
                total += weight * float(service['price_per_kg'])
            
            # Create order
            sql = """
                INSERT INTO orders (user_id, weight, total_estimate, status) 
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (session['user']['user_id'], weight, total, 'Pending'))
            order_id = cursor.lastrowid
            
            # Add order services
            for service_id in service_ids:
                cursor.execute("""
                    INSERT INTO order_services (order_id, service_id) 
                    VALUES (%s, %s)
                """, (order_id, service_id))
            
            connection.commit()
            
            flash(f"Order submitted successfully! Estimated cost: ₱{total:.2f}", "success")
            
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
    finally:
        connection.close()
    
    return redirect(url_for('user_dashboard'))

@app.route('/user_orders')
def my_orders():
    if 'user' not in session or session['user']['role'] != 'user':
        return redirect(url_for('login'))
    
    user_id = session['user']['user_id']
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Get order stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed
                FROM orders 
                WHERE user_id=%s
            """, (user_id,))
            stats = cursor.fetchone()
            
            # Calculate pagination
            total_orders = stats['total'] if stats else 0
            total_pages = math.ceil(total_orders / per_page)
            offset = (page - 1) * per_page
            
            # Get orders with pagination
            cursor.execute("""
                SELECT o.*, 
                       GROUP_CONCAT(s.service_name) as services_list
                FROM orders o
                LEFT JOIN order_services os ON o.order_id = os.order_id
                LEFT JOIN services s ON os.service_id = s.service_id
                WHERE o.user_id=%s
                GROUP BY o.order_id
                ORDER BY o.created_at DESC
                LIMIT %s OFFSET %s
            """, (user_id, per_page, offset))
            orders = cursor.fetchall()
            
            # Format data for display
            for order in orders:
                order['order_code'] = f"ORD-{order['order_id']:04d}"
                if order['services_list']:
                    order['services_list'] = order['services_list'].split(',')
                else:
                    order['services_list'] = []
                
    finally:
        connection.close()
    
    return render_template('user_orders.html',
                         orders=orders,
                         total_orders=stats['total'] if stats else 0,
                         pending_orders=stats['pending'] if stats else 0,
                         in_progress_orders=stats['in_progress'] if stats else 0,
                         completed_orders=stats['completed'] if stats else 0,
                         page=page,
                         total_pages=total_pages)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user' not in session or session['user']['role'] != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('landing'))

if __name__ == '__main__':
    app.run(debug=True)