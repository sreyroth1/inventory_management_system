from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from models import db, Product
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db.init_app(app)

# Routes for HTML pages
@app.route('/')
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
def add_product_page():
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
def edit_product_page(id):
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

@app.route('/report')
def reports_page():
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

# API Routes (Renamed to avoid conflicts)
@app.route('/api/products', methods=['GET'])
def api_get_products():
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

@app.route('/api/products', methods=['POST'])
def api_add_product():
    try:
        data = request.get_json()
        
        # Check if SKU already exists
        if Product.query.filter_by(sku=data['sku']).first():
            return jsonify({'error': 'SKU already exists'}), 400
            
        product = Product(
            name=data['name'],
            category=data['category'],
            price=float(data['price']),
            quantity=int(data['quantity']),
            description=data.get('description', ''),
            sku=data['sku']
        )
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify(product.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:id>', methods=['GET'])
def api_get_product(id):
    try:
        product = Product.query.get_or_404(id)
        return jsonify(product.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:id>', methods=['PUT'])
def api_update_product(id):
    try:
        product = Product.query.get_or_404(id)
        data = request.get_json()
        
        # Check if SKU already exists (excluding current product)
        if 'sku' in data and data['sku'] != product.sku:
            if Product.query.filter_by(sku=data['sku']).first():
                return jsonify({'error': 'SKU already exists'}), 400
        
        product.name = data.get('name', product.name)
        product.category = data.get('category', product.category)
        product.price = float(data.get('price', product.price))
        product.quantity = int(data.get('quantity', product.quantity))
        product.description = data.get('description', product.description)
        product.sku = data.get('sku', product.sku)
        
        db.session.commit()
        return jsonify(product.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:id>', methods=['DELETE'])
def api_delete_product(id):
    try:
        product = Product.query.get_or_404(id)
        db.session.delete(product)
        db.session.commit()
        return jsonify({'message': 'Product deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports')
def api_get_reports():
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

@app.route('/api/categories')
def api_get_categories():
    try:
        categories = db.session.query(Product.category).distinct().all()
        return jsonify([cat[0] for cat in categories])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)