from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from decimal import Decimal, ROUND_HALF_UP
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///invoices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

# Models
class CompanySettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    address = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    logo_path = db.Column(db.String(200))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(40))
    customer_name = db.Column(db.String(120))
    date = db.Column(db.String(50))
    discount = db.Column(db.Float, nullable=True)
    total = db.Column(db.Float)
    status = db.Column(db.String(20))
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'))
    description = db.Column(db.String(300))
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)

# Create tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    invoices = Invoice.query.order_by(Invoice.id.desc()).all()
    total_invoice = len(invoices)
    total_nominal = sum(Decimal(str(i.total)) for i in invoices) if invoices else Decimal('0.00')
    total_lunas = sum(Decimal(str(i.total)) for i in invoices if i.status == 'LUNAS') if invoices else Decimal('0.00')
    # convert to floats for display
    return render_template('index.html', invoices=invoices,
                           total_invoice=total_invoice,
                           total_nominal=float(total_nominal),
                           total_lunas=float(total_lunas))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    settings = CompanySettings.query.first()
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        phone = request.form['phone']

        logo_file = request.files.get('logo')
        logo_path = settings.logo_path if settings else None
        if logo_file and logo_file.filename:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            logo_filename = 'logo.png'
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)
            logo_file.save(logo_path)

        if settings:
            settings.name = name
            settings.address = address
            settings.phone = phone
            settings.logo_path = logo_path
        else:
            settings = CompanySettings(name=name, address=address, phone=phone, logo_path=logo_path)
            db.session.add(settings)
        db.session.commit()
        flash('Pengaturan perusahaan disimpan!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', settings=settings)

@app.route('/create', methods=['GET', 'POST'])
def create_invoice():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        # Item lists
        descs = request.form.getlist('item_description')
        qtys = request.form.getlist('item_quantity')
        prices = request.form.getlist('item_price')

        # Calculate subtotal using Decimal
        subtotal = Decimal('0.00')
        items_to_save = []
        for d, q, p in zip(descs, qtys, prices):
            if not d or d.strip() == '':
                continue
            try:
                qd = Decimal(q)
                pd = Decimal(p)
            except:
                continue
            line_total = (qd * pd).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            subtotal += line_total
            items_to_save.append({
                'description': d.strip(),
                'quantity': float(qd),
                'price': float(pd),
                'line_total': float(line_total)
            })

        # Discount (optional)
        discount_raw = request.form.get('discount', '').strip()
        if discount_raw != '':
            try:
                discount_dec = Decimal(discount_raw)
                discount_val = float(discount_dec)
            except:
                discount_dec = Decimal('0.00')
                discount_val = None
        else:
            discount_dec = Decimal('0.00')
            discount_val = None

        total_dec = subtotal - (discount_dec if discount_val is not None else Decimal('0.00'))
        total_dec = total_dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # basic validation: must have at least one item
        if len(items_to_save) == 0:
            flash('Anda harus memasukkan minimal 1 item pada invoice.', 'danger')
            return redirect(url_for('create_invoice'))

        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        date = datetime.now().strftime("%Y-%m-%d")

        new_inv = Invoice(invoice_number=invoice_number,
                          customer_name=customer_name,
                          date=date,
                          discount=discount_val,
                          total=float(total_dec),
                          status=request.form.get('status', 'BELUM LUNAS'))
        db.session.add(new_inv)
        db.session.flush()  # supaya dapat id

        for it in items_to_save:
            inv_item = InvoiceItem(invoice_id=new_inv.id,
                                   description=it['description'],
                                   quantity=it['quantity'],
                                   price=it['price'])
            db.session.add(inv_item)

        db.session.commit()
        flash('Invoice baru berhasil dibuat!', 'success')
        return redirect(url_for('view_invoice', id=new_inv.id))

    return render_template('create_invoice.html')

@app.route('/invoice/<int:id>')
def view_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    settings = CompanySettings.query.first()
    # compute subtotal from items to ensure consistency
    subtotal = sum(Decimal(str(it.quantity)) * Decimal(str(it.price)) for it in invoice.items) if invoice.items else Decimal('0.00')
    subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    discount = Decimal(str(invoice.discount)) if invoice.discount is not None else None
    total = Decimal(str(invoice.total)).quantize(Decimal('0.01')) if invoice.total is not None else (subtotal - (discount or Decimal('0.00')))
    return render_template('view_invoice.html', invoice=invoice, settings=settings,
                           subtotal=float(subtotal), discount=float(discount) if discount is not None else None, total=float(total))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
