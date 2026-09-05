import os
from datetime import datetime
import werkzeug.utils
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from models import db, User, Dish, Order, OrderItem, Reservation
import logging

logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='utf-8'
)

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SECRET_KEY'] = 'khachapuri_secret_key_2026'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['CACHE_TYPE'] = 'SimpleCache'
app.config['CACHE_DEFAULT_TIMEOUT'] = 60

csrf = CSRFProtect(app)
cache = Cache(app)

SUPER_ADMIN_EMAIL = 'nezzok777@gmail.com'

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def save_image(file):
    if not file or file.filename == '':
        return 'default.jpg'

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    filename = werkzeug.utils.secure_filename(file.filename)
    filename = os.path.splitext(filename)[0] + '.webp'
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    img = Image.open(file)
    img.convert('RGB').save(filepath, 'WEBP', optimize=True, quality=80)

    return filename


with app.app_context():
    db.create_all()

    if Dish.query.count() < 10:
        Dish.query.delete()
        sample_dishes = [
            Dish(title='Хачапурі по-аджарськи', category='Хачапурі', price=220.0,
                 description='Класичний човник із сиром сулугуні, вершковим маслом та сирим жовтком.',
                 image='default1.jpg'),
            Dish(title='Хачапурі по-мегрельськи', category='Хачапурі', price=240.0,
                 description='Запечений круглий коржик із подвійною порцією сиру сулугуні.', image='default2.jpg'),
            Dish(title='Хачапурі по-імператорськи', category='Хачапурі', price=210.0,
                 description='Елітна випічка з трьома видами сиру та трьома відбірними жовтками.', image='default3.jpg'),
            Dish(title='Кубдарі', category='Хачапурі', price=260.0,
                 description='Грузинський пиріг із соковитим рубленим м’ясом свинини та яловичини зі спеціями.',
                 image='default4.jpg'),
            Dish(title='Хінкалі з яловичиною (5 шт)', category='Гаряче', price=190.0,
                 description='Соковиті хінкалі з духмяним м’ясним фаршем та зеленню.', image='default5.jpg'),
            Dish(title='Хінкалі з сиром (5 шт)', category='Гаряче', price=180.0,
                 description='Ніжні хінкалі з начинкою з сулугуні та імеретинського сиру.', image='default5.jpg'),
            Dish(title='Оджахурі зі свининою', category='Гаряче', price=270.0,
                 description='Смажене м’ясо з картоплею, цибулею, томатами та грузинськими спеціями.',
                 image='default5.jpg'),
            Dish(title='Чашушулі', category='Гаряче', price=250.0,
                 description='Ніжна телятина, тушкована в томатному соусі з болгарським перцем та зеленню.',
                 image='default5.jpg'),
            Dish(title='Сапераві (червоне сухе)', category='Вино', price=450.0,
                 description='Традиційне грузинське червоне вино з багатим смаком, 0.75 л.', image='default6.jpg'),
            Dish(title='Цинандалі (біле сухе)', category='Вино', price=420.0,
                 description='Класичне біле вино з фруктово-квітковим ароматом, 0.75 л.', image='default7.jpg'),
            Dish(title='Лимонад Натахтарі (Тархун)', category='Напої', price=75.0,
                 description='Освіжаючий грузинський лимонад, 0.5 л.', image='default8.jpg'),
            Dish(title='Лимонад Натахтарі (Маракуя)', category='Напої', price=75.0,
                 description='Соковитий ароматний лимонад зі смаком Маракуя, 0.5 л.', image='default9.jpg')
        ]
        db.session.add_all(sample_dishes)
        db.session.commit()


@app.route('/')
def index():
    dishes = Dish.query.all()
    return render_template('index.html', dishes=dishes)


@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        date = request.form.get('date')
        time = request.form.get('time')
        guests = int(request.form.get('guests'))
        user_id = current_user.id if current_user.is_authenticated else None

        new_booking = Reservation(
            user_id=user_id,
            name=name,
            phone=phone,
            date=date,
            time=time,
            guests=guests
        )
        db.session.add(new_booking)
        db.session.commit()
        flash("Столик успішно заброньовано!", "success")
        return redirect(url_for('index'))

    return render_template('booking.html')


@app.route('/cart/add/<int:dish_id>', methods=['POST'])
def add_to_cart(dish_id):
    cart = session.get('cart', {})
    str_id = str(dish_id)
    cart[str_id] = cart.get(str_id, 0) + 1
    session['cart'] = cart
    flash("Страва успішно додана до кошика!", "success")
    return redirect(url_for('index'))


@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    cart_items = []
    total_sum = 0
    for str_id, quantity in cart.items():
        dish = Dish.query.get(int(str_id))
        if dish:
            item_total = dish.price * quantity
            total_sum += item_total
            cart_items.append({
                'id': dish.id,
                'title': dish.title,
                'price': dish.price,
                'quantity': quantity,
                'total': item_total
            })
    return render_template('cart.html', cart_items=cart_items, total_sum=total_sum)


@app.route('/cart/remove/<int:dish_id>', methods=['POST'])
def remove_from_cart(dish_id):
    cart = session.get('cart', {})
    str_id = str(dish_id)
    if str_id in cart:
        del cart[str_id]
        session['cart'] = cart
        flash("Страва видалена з кошика!", "warning")
    return redirect(url_for('cart'))


@app.route('/cart/checkout', methods=['POST'])
@login_required
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Ваш кошик порожній!', 'warning')
        return redirect(url_for('cart'))

    total_price = 0
    new_order = Order(user_id=current_user.id, total_price=0)
    db.session.add(new_order)
    db.session.flush()

    for dish_id_str, qty in cart.items():
        dish = Dish.query.get(int(dish_id_str))
        if dish:
            item_total = dish.price * qty
            total_price += item_total
            order_item = OrderItem(
                order_id=new_order.id,
                dish_id=dish.id,
                dish_title=dish.title,
                price=dish.price,
                quantity=qty
            )
            db.session.add(order_item)

    new_order.total_price = total_price
    db.session.commit()

    logging.info(f"Створено нове замовлення №{new_order.id} користувачем ID {current_user.id}.")

    session['cart'] = {}
    flash('Замовлення успішно оформлено!', 'success')
    return redirect(url_for('profile'))


@app.route('/profile')
@login_required
def profile():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    reservations = Reservation.query.filter_by(user_id=current_user.id).order_by(Reservation.created_at.desc()).all()
    return render_template('profile.html', orders=orders, reservations=reservations)


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin:
        flash("У вас немає доступу!", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        if 'add_dish' in request.form:
            title = request.form.get('title')
            category = request.form.get('category')
            price = float(request.form.get('price'))
            description = request.form.get('description')
            file = request.files.get('image')
            image_filename = save_image(file) if file else 'default.jpg'

            new_dish = Dish(title=title, category=category, price=price, description=description, image=image_filename)
            db.session.add(new_dish)
            db.session.commit()
            cache.clear()
            flash('Страва успішно додана!', 'success')
            return redirect(url_for('admin'))

        if 'grant_admin' in request.form:
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_admin = True
                db.session.commit()
                flash(f'Користувач {user.username} тепер адмін!', 'success')
            else:
                flash('Користувача з таким email не знайдено!', 'danger')
            return redirect(url_for('admin'))

    dishes = Dish.query.all()
    admins = User.query.filter_by(is_admin=True).all()
    is_super_admin = (current_user.email == 'admin@gmail.com') or (current_user.id == 1)

    reservations = Reservation.query.order_by(Reservation.created_at.desc()).all()
    return render_template('admin.html', dishes=dishes, admins=admins, is_super_admin=is_super_admin,
                           reservations=reservations)


@app.route('/admin/revoke_admin/<int:user_id>', methods=['POST'])
@login_required
def revoke_admin(user_id):
    if current_user.email != SUPER_ADMIN_EMAIL:
        flash("Тільки головний адміністратор може забирати права!", "danger")
        return redirect(url_for('admin'))

    user = User.query.get(user_id)
    if user and user.email != SUPER_ADMIN_EMAIL:
        user.is_admin = False
        db.session.commit()
        flash(f"Права адміністратора для {user.username} скасовано!", "warning")

    return redirect(url_for('admin'))


@app.route('/admin/delete/<int:dish_id>', methods=['POST'])
@login_required
def delete_dish(dish_id):
    if not current_user.is_admin:
        flash('У вас немає доступу до цієї дії!', 'danger')
        return redirect(url_for('index'))

    dish = Dish.query.get_or_404(dish_id)
    db.session.delete(dish)
    db.session.commit()
    cache.clear()

    logging.info(f"Адміністратор {current_user.username} видалив страву ID {dish_id}.")

    flash('Страва успішно видалена!', 'warning')
    return redirect(url_for('admin'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash("Користувач з таким email вже існує!", "danger")
            return render_template('register.html')

        hashed_password = generate_password_hash(password, method='scrypt')

        is_admin_user = (email == SUPER_ADMIN_EMAIL)
        new_user = User(username=username, email=email, password=hashed_password, is_admin=is_admin_user)

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash("Ви успішно зареєструвалися та увійшли!", "success")
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            logging.info(f"Користувач {user.username} успішно увійшов у систему.")
            flash('Ви успішно увійшли!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Невірний email або пароль', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Ви вийшли з акаунта", "info")
    return redirect(url_for('index'))


@app.route('/admin/edit/<int:dish_id>', methods=['GET', 'POST'])
@login_required
def edit_dish(dish_id):
    if not current_user.is_admin:
        flash("У вас немає доступу до цієї сторінки!", "danger")
        return redirect(url_for('index'))

    dish = Dish.query.get_or_404(dish_id)

    if request.method == 'POST':
        dish.title = request.form.get('title')
        dish.category = request.form.get('category')
        dish.price = float(request.form.get('price'))
        dish.description = request.form.get('description')

        file = request.files.get('image')
        if file and file.filename != '':
            dish.image = save_image(file)

        db.session.commit()
        cache.clear()
        flash("Інформацію про страву успішно оновлено!", "success")
        return redirect(url_for('admin'))

    return render_template('edit_dish.html', dish=dish)

@app.route('/position/<int:dish_id>')
def position(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    return render_template('position.html', dish=dish)

@app.route('/my_order/<int:order_id>')
@login_required
def my_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin:
        flash("У вас немає доступу до цього замовлення!", "danger")
        return redirect(url_for('profile'))
    return render_template('my_order.html', order=order)

@app.route('/my_order/cancel/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin:
        flash("У вас немає прав скасувати це замовлення!", "danger")
        return redirect(url_for('profile'))

    OrderItem.query.filter_by(order_id=order.id).delete()
    db.session.delete(order)
    db.session.commit()
    flash("Замовлення успішно скасовано!", "warning")
    return redirect(url_for('profile'))

@app.route('/admin/reservation/cancel/<int:res_id>', methods=['POST'])
@login_required
def cancel_reservation(res_id):
    if not current_user.is_admin:
        flash("У вас немає доступу до цієї дії!", "danger")
        return redirect(url_for('index'))

    res = Reservation.query.get_or_404(res_id)
    db.session.delete(res)
    db.session.commit()
    flash("Бронювання успішно скасовано!", "warning")
    return redirect(url_for('admin'))


if __name__ == '__main__':
    app.run(debug=True)