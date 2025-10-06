
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///invoices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

class CompanySettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    address = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    logo_path = db.Column(db.String(200))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20))
    customer_name = db.Column(db.String(120))
    date = db.Column(db.String(50))
    discount = db.Column(db.Float)
    total = db.Column(db.Float)
    status = db.Column(db.String(20))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    invoices = Invoice.query.all()
    total_invoice = len(invoices)
    total_nominal = sum(i.total for i in invoices)
    total_lunas = sum(i.total for i in invoices if i.status == 'LUNAS')
    return render_template('index.html', invoices=invoices,
                           total_invoice=total_invoice,
                           total_nominal=total_nominal,
                           total_lunas=total_lunas)

@app.route('/settings', methods=['GET','POST'])
def settings():
    settings = CompanySettings.query.first()
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        phone = request.form['phone']
        logo_file = request.files.get('logo')
        logo_path = settings.logo_path if settings else None
        if logo_file and logo_file.filename:
            logo_filename = 'logo.png'
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)
            logo_file.save(logo_path)
        if settings:
            settings.name = name
            settings.address = address
            settings.phone = phone
            settings.logo_path = logo_path
        else:
            settings = CompanySettings(name=name,address=address,phone=phone,logo_path=logo_path)
            db.session.add(settings)
        db.session.commit()
        flash('Pengaturan perusahaan disimpan!','success')
        return redirect(url_for('settings'))
    return render_template('settings.html',settings=settings)

@app.route('/create',methods=['GET','POST'])
def create_invoice():
    if request.method=='POST':
        customer_name=request.form['customer_name']
        total=float(request.form['total'])
        discount=request.form.get('discount')
        discount=float(discount) if discount else None
        status=request.form['status']
        invoice_number=f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        date=datetime.now().strftime("%Y-%m-%d")
        new_invoice=Invoice(invoice_number=invoice_number,customer_name=customer_name,date=date,discount=discount,total=total,status=status)
        db.session.add(new_invoice)
        db.session.commit()
        flash('Invoice baru berhasil dibuat!','success')
        return redirect(url_for('index'))
    return render_template('create_invoice.html')

@app.route('/invoice/<int:id>')
def view_invoice(id):
    invoice=Invoice.query.get_or_404(id)
    settings=CompanySettings.query.first()
    return render_template('view_invoice.html',invoice=invoice,settings=settings)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],filename)

if __name__=='__main__':
    port=int(os.environ.get("PORT",5000))
    app.run(host='0.0.0.0',port=port)
