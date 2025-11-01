from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Product, User, Order, OrderItem
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db.init_app(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'error'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin required decorator
def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash('Admin access required.', 'error')
            return redirect('/')
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Initialize database with demo data
def init_database():
    """Initialize the database with demo users"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if demo users already exist
        if not User.query.filter_by(username='admin').first():
            # Create admin user
            admin_user = User(
                username='admin',
                email='admin@inventory.com',
                first_name='System',
                last_name='Administrator',
                role='admin'
            )
            admin_user.set_password('password123')
            db.session.add(admin_user)
            
            # Create regular user
            regular_user = User(
                username='user',
                email='user@inventory.com',
                first_name='Regular',
                last_name='User',
                role='user'
            )
            regular_user.set_password('password123')
            db.session.add(regular_user)
            
            db.session.commit()
            print("Database initialized with demo users!")
            print("Admin login: admin / password123")
            print("User login: user / password123")

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect('/')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = bool(request.form.get('remember_me'))
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'error')
                return render_template('login.html')
            
            # Update last login time
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            login_user(user, remember=remember_me)
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect('/')
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect('/login')

# Initialize demo user (run this once)
@app.route('/init-demo-user')
def init_demo_user_route():
    init_database()
    flash('Demo users created successfully! Admin: admin/password123, User: user/password123', 'success')
    return redirect('/login')

# Main Application Routes
@app.route('/')
@login_required
def dashboard():
    # Get search and filter parameters
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    # Build query
    query = Product.query
    
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    if category:
        query = query.filter(Product.category == category)
    
    products = query.order_by(Product.updated_at.desc()).all()
    
    # Get all categories for filter dropdown
    categories = db.session.query(Product.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    # Calculate statistics
    total_products = len(products)
    total_quantity = sum(product.quantity for product in products)
    total_value = sum(product.total_value for product in products)
    total_categories = len(set(product.category for product in products))
    
    return render_template('dashboard.html', 
                         products=products,
                         categories=categories,
                         search=search,
                         selected_category=category,
                         total_products=total_products,
                         total_quantity=total_quantity,
                         total_value=total_value,
                         total_categories=total_categories)

@app.route('/add-product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            category = request.form.get('category')
            price = request.form.get('price')
            quantity = request.form.get('quantity')
            description = request.form.get('description', '')
            sku = request.form.get('sku')
            
            # Validate required fields
            if not all([name, category, price, quantity, sku]):
                flash('All fields marked with * are required.', 'error')
                return render_template('add_product.html')
            
            # Convert price and quantity
            try:
                price = float(price)
                quantity = int(quantity)
            except ValueError:
                flash('Price must be a number and quantity must be an integer.', 'error')
                return render_template('add_product.html')
            
            # Check if SKU already exists
            if Product.query.filter_by(sku=sku).first():
                flash('SKU already exists. Please use a unique SKU.', 'error')
                return render_template('add_product.html')
            
            # Create new product
            product = Product(
                name=name,
                category=category,
                price=price,
                quantity=quantity,
                description=description,
                sku=sku
            )
            
            db.session.add(product)
            db.session.commit()
            
            flash('Product added successfully!', 'success')
            return redirect('/')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding product: {str(e)}', 'error')
            return render_template('add_product.html')
    
    return render_template('add_product.html')

@app.route('/edit-product/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            category = request.form.get('category')
            price = request.form.get('price')
            quantity = request.form.get('quantity')
            description = request.form.get('description', '')
            new_sku = request.form.get('sku')
            
            # Validate required fields
            if not all([name, category, price, quantity, new_sku]):
                flash('All fields marked with * are required.', 'error')
                return render_template('edit_product.html', product=product)
            
            # Convert price and quantity
            try:
                price = float(price)
                quantity = int(quantity)
            except ValueError:
                flash('Price must be a number and quantity must be an integer.', 'error')
                return render_template('edit_product.html', product=product)
            
            # Check if SKU already exists (excluding current product)
            if new_sku != product.sku and Product.query.filter_by(sku=new_sku).first():
                flash('SKU already exists. Please use a unique SKU.', 'error')
                return render_template('edit_product.html', product=product)
            
            # Update product
            product.name = name
            product.category = category
            product.price = price
            product.quantity = quantity
            product.description = description
            product.sku = new_sku
            product.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('Product updated successfully!', 'success')
            return redirect('/')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'error')
            return render_template('edit_product.html', product=product)
    
    return render_template('edit_product.html', product=product)

@app.route('/delete-product/<int:id>')
@login_required
def delete_product(id):
    try:
        product = Product.query.get_or_404(id)
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
    
    return redirect('/')

@app.route('/view-product/<int:id>')
@login_required
def view_product(id):
    product = Product.query.get_or_404(id)
    return render_template('view_product.html', product=product)

# Order Management Routes
@app.route('/orders')
@login_required
def orders():
    status = request.args.get('status', '')
    
    query = Order.query
    
    if status:
        query = query.filter(Order.status == status)
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    # Calculate order statistics
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    completed_orders = Order.query.filter_by(status='completed').count()
    total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
    
    return render_template('orders.html',
                         orders=orders,
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         completed_orders=completed_orders,
                         total_revenue=total_revenue)

@app.route('/create-order', methods=['GET', 'POST'])
@login_required
def create_order():
    if request.method == 'POST':
        try:
            # Get form data
            customer_name = request.form.get('customer_name')
            customer_email = request.form.get('customer_email', '')
            customer_phone = request.form.get('customer_phone', '')
            status = request.form.get('status', 'pending')
            notes = request.form.get('notes', '')
            
            # Get order items
            product_ids = request.form.getlist('product_id[]')
            product_names = request.form.getlist('product_name[]')
            product_prices = request.form.getlist('product_price[]')
            quantities = request.form.getlist('quantity[]')
            
            if not customer_name:
                flash('Customer name is required.', 'error')
                return render_template('create_order.html')
            
            if not product_ids:
                flash('At least one product is required.', 'error')
                return render_template('create_order.html')
            
            # Calculate total amount
            total_amount = 0
            order_items = []
            
            for i in range(len(product_ids)):
                product_id = int(product_ids[i])
                product_name = product_names[i]
                product_price = float(product_prices[i])
                quantity = int(quantities[i])
                
                # Check product stock
                product = Product.query.get(product_id)
                if not product:
                    flash(f'Product {product_name} not found.', 'error')
                    return render_template('create_order.html')
                
                if product.quantity < quantity:
                    flash(f'Insufficient stock for {product_name}. Available: {product.quantity}', 'error')
                    return render_template('create_order.html')
                
                item_total = product_price * quantity
                total_amount += item_total
                
                order_items.append({
                    'product_id': product_id,
                    'product_name': product_name,
                    'product_price': product_price,
                    'quantity': quantity,
                    'total_price': item_total
                })
            
            # Create order
            order = Order(
                order_number=Order.generate_order_number(),
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                status=status,
                total_amount=total_amount,
                notes=notes
            )
            
            db.session.add(order)
            db.session.flush()  # Get order ID
            
            # Create order items and update product quantities
            for item_data in order_items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item_data['product_id'],
                    product_name=item_data['product_name'],
                    product_price=item_data['product_price'],
                    quantity=item_data['quantity'],
                    total_price=item_data['total_price']
                )
                db.session.add(order_item)
                
                # Update product quantity
                product = Product.query.get(item_data['product_id'])
                product.quantity -= item_data['quantity']
            
            db.session.commit()
            
            flash('Order created successfully!', 'success')
            return redirect('/orders')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating order: {str(e)}', 'error')
            return render_template('create_order.html')
    
    return render_template('create_order.html')

@app.route('/view-order/<int:id>')
@login_required
def view_order(id):
    order = Order.query.get_or_404(id)
    return render_template('view_order.html', order=order)

@app.route('/edit-order/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_order(id):
    order = Order.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            order.customer_name = request.form.get('customer_name')
            order.customer_email = request.form.get('customer_email', '')
            order.customer_phone = request.form.get('customer_phone', '')
            order.status = request.form.get('status', 'pending')
            order.notes = request.form.get('notes', '')
            order.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Order updated successfully!', 'success')
            return redirect('/orders')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating order: {str(e)}', 'error')
    
    return render_template('edit_order.html', order=order)

@app.route('/delete-order/<int:id>')
@admin_required
def delete_order(id):
    try:
        order = Order.query.get_or_404(id)
        
        # Restore product quantities
        for item in order.items:
            product = Product.query.get(item.product_id)
            if product:
                product.quantity += item.quantity
        
        db.session.delete(order)
        db.session.commit()
        flash('Order deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting order: {str(e)}', 'error')
    
    return redirect('/orders')

# Reports Route
@app.route('/report')
@login_required
def report():
    try:
        # Get all products for calculations
        products = Product.query.all()
        
        # Basic statistics
        total_products = len(products)
        total_quantity = sum(product.quantity for product in products)
        total_value = sum(product.total_value for product in products)
        
        # Category breakdown
        categories = {}
        for product in products:
            if product.category not in categories:
                categories[product.category] = {
                    'count': 0,
                    'total_quantity': 0,
                    'total_value': 0
                }
            categories[product.category]['count'] += 1
            categories[product.category]['total_quantity'] += product.quantity
            categories[product.category]['total_value'] += product.total_value
        
        # Convert to list and calculate averages
        category_list = []
        for category_name, data in categories.items():
            avg_price = data['total_value'] / data['count'] if data['count'] > 0 else 0
            category_list.append({
                'category': category_name,
                'count': data['count'],
                'total_quantity': data['total_quantity'],
                'total_value': data['total_value'],
                'avg_price': avg_price
            })
        
        # Calculate quick stats
        if category_list:
            top_category = max(category_list, key=lambda x: x['count'])
            highest_value = max(category_list, key=lambda x: x['total_value'])
            avg_quantity = sum(cat['total_quantity'] for cat in category_list) / len(category_list)
            total_categories = len(category_list)
        else:
            top_category = {'category': 'N/A'}
            highest_value = {'total_value': 0}
            avg_quantity = 0
            total_categories = 0
        
        return render_template('report.html', 
                             total_products=total_products,
                             total_quantity=total_quantity,
                             total_value=total_value,
                             categories=category_list,
                             top_category=top_category,
                             highest_value=highest_value,
                             avg_quantity=avg_quantity,
                             total_categories=total_categories)
    except Exception as e:
        return render_template('report.html', error=str(e))

# API Routes
@app.route('/api/products', methods=['GET'])
@login_required
def api_products():
    try:
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        
        query = Product.query
        
        if search:
            query = query.filter(Product.name.ilike(f'%{search}%'))
        if category:
            query = query.filter(Product.category == category)
            
        products = query.order_by(Product.updated_at.desc()).all()
        return jsonify([product.to_dict() for product in products])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders', methods=['GET'])
@login_required
def api_orders():
    try:
        status = request.args.get('status', '')
        
        query = Order.query
        if status:
            query = query.filter(Order.status == status)
            
        orders = query.order_by(Order.created_at.desc()).all()
        return jsonify([order.to_dict() for order in orders])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports')
@login_required
def api_reports():
    try:
        total_products = Product.query.count()
        total_quantity = db.session.query(db.func.sum(Product.quantity)).scalar() or 0
        total_value = db.session.query(db.func.sum(Product.price * Product.quantity)).scalar() or 0
        
        # Category breakdown
        categories = db.session.query(
            Product.category,
            db.func.count(Product.id).label('count'),
            db.func.sum(Product.quantity).label('total_quantity'),
            db.func.sum(Product.price * Product.quantity).label('total_value')
        ).group_by(Product.category).all()
        
        category_data = [
            {
                'category': cat[0],
                'count': cat[1],
                'total_quantity': cat[2],
                'total_value': float(cat[3]) if cat[3] else 0
            }
            for cat in categories
        ]
        
        return jsonify({
            'total_products': total_products,
            'total_quantity': total_quantity,
            'total_value': float(total_value),
            'categories': category_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Simple Admin Route - Only User Management
@app.route('/admin')
@admin_required
def admin_dashboard():
    return redirect('/admin/users')

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)

# Admin API Routes for User Management
@app.route('/admin/api/users', methods=['GET', 'POST'])
@admin_required
def api_users():
    if request.method == 'GET':
        users = User.query.all()
        return jsonify([{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_active': user.is_active,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat()
        } for user in users])
    
    elif request.method == 'POST':
        data = request.get_json()
        
        # Check if username or email already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            role=data['role'],
            is_active=data.get('is_active', True) == 'true'
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'message': 'User created successfully'})

@app.route('/admin/api/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def api_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'GET':
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_active': user.is_active
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        # Check if username or email already exists (excluding current user)
        if User.query.filter(User.username == data['username'], User.id != user_id).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter(User.email == data['email'], User.id != user_id).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user.username = data['username']
        user.email = data['email']
        user.first_name = data.get('first_name', '')
        user.last_name = data.get('last_name', '')
        user.role = data['role']
        user.is_active = data.get('is_active', True) == 'true'
        user.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'message': 'User updated successfully'})
    
    elif request.method == 'DELETE':
        if user_id == current_user.id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'User deleted successfully'})

@app.route('/admin/api/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot change your own status'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    
    return jsonify({'message': f'User {"activated" if user.is_active else "deactivated"} successfully'})

# Initialize the database and run the app
if __name__ == '__main__':
    # Initialize database with demo data
    init_database()
    app.run(debug=True)