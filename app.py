import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from models import db, User, Category, Dish, Reservation, Order, OrderItem
import logging


logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    encoding='utf-8'
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

TOTAL_SEATS = 50


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def index():
    cat_id = request.args.get('cat_id', type=int)
    categories = Category.query.all()
    if cat_id:
        dishes = Dish.query.filter_by(category_id=cat_id).all()
    else:
        dishes = Dish.query.all()
    return render_template('index.html', categories=categories, dishes=dishes, current_cat=cat_id)


@app.route('/position/<int:dish_id>')
def position(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    return render_template('position.html', dish=dish)


@app.route('/cart')
def cart():
    cart_data = session.get('cart', {})
    cart_items = []
    total_sum = 0
    for dish_id_str, qty in cart_data.items():
        dish = Dish.query.get(int(dish_id_str))
        if dish:
            item_total = dish.price * qty
            total_sum += item_total
            cart_items.append({
                'id': dish.id,
                'title': dish.title,
                'price': dish.price,
                'quantity': qty,
                'total': item_total
            })
    return render_template('cart.html', cart_items=cart_items, total_sum=total_sum)


@app.route('/add_to_cart/<int:dish_id>', methods=['POST'])
def add_to_cart(dish_id):
    cart_data = session.get('cart', {})
    dish_id_str = str(dish_id)
    cart_data[dish_id_str] = cart_data.get(dish_id_str, 0) + 1
    session['cart'] = cart_data
    flash('Страва додана в кошик!', 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/remove_from_cart/<int:dish_id>', methods=['POST'])
def remove_from_cart(dish_id):
    cart_data = session.get('cart', {})
    dish_id_str = str(dish_id)
    if dish_id_str in cart_data:
        del cart_data[dish_id_str]
        session['cart'] = cart_data
        flash('Страва видалена з кошика.', 'info')
    return redirect(url_for('cart'))


@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart_data = session.get('cart', {})
    if not cart_data:
        flash('Ваш кошик порожній.', 'warning')
        return redirect(url_for('index'))

    total_sum = 0
    items_to_create = []

    for dish_id_str, qty in cart_data.items():
        dish = Dish.query.get(int(dish_id_str))
        if dish:
            item_total = dish.price * qty
            total_sum += item_total
            items_to_create.append((dish, qty))

    if not items_to_create:
        flash('Помилка при оформленні замовлення.', 'danger')
        return redirect(url_for('cart'))

    new_order = Order(user_id=current_user.id, total_price=total_sum, status='В обробці')
    db.session.add(new_order)
    db.session.flush()

    for dish, qty in items_to_create:
        order_item = OrderItem(
            order_id=new_order.id,
            dish_id=dish.id,
            dish_title=dish.title,
            price=dish.price,
            quantity=qty
        )
        db.session.add(order_item)

    db.session.commit()
    session.pop('cart', None)
    flash('Замовлення успішно оформлене!', 'success')
    return redirect(url_for('profile'))


@app.route('/booking', methods=['GET', 'POST'])
def booking():
    today_date = datetime.now().strftime('%Y-%m-%d')
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        date = request.form.get('date')
        time = request.form.get('time')
        guests = int(request.form.get('guests', 1))

        existing_reservations = Reservation.query.filter_by(date=date).all()
        booked_seats = sum(r.guests for r in existing_reservations)
        available_seats = TOTAL_SEATS - booked_seats

        if guests > available_seats:
            flash(f'На цю дату місця закінчуються! Всіх місць {TOTAL_SEATS}, вільно лише {available_seats}.', 'danger')
            return redirect(url_for('booking'))

        res = Reservation(
            user_id=current_user.id if current_user.is_authenticated else None,
            name=name,
            phone=phone,
            date=date,
            time=time,
            guests=guests
        )
        db.session.add(res)
        db.session.commit()
        flash('Столик успішно заброньовано!', 'success')
        return redirect(url_for('profile') if current_user.is_authenticated else url_for('index'))

    return render_template('booking.html', today_date=today_date)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Ви успішно увійшли!', 'success')
            return redirect(url_for('index'))
        flash('Невірний email або пароль.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Користувач з таким email вже існує.', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)

        if email == 'nezzok777@gmail.com':
            user.is_admin = True
            user.is_superadmin = True

        db.session.add(user)
        db.session.commit()
        flash('Реєстрація успішна! Увійдіть у систему.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Ви вийшли з акаунту.', 'info')
    return redirect(url_for('index'))


@app.route('/profile')
@login_required
def profile():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    reservations = Reservation.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', orders=orders, reservations=reservations)


@app.route('/my_order/<int:order_id>')
@login_required
def my_order(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    return render_template('order_details.html', order=order)


@app.route('/cancel_order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    db.session.delete(order)
    db.session.commit()
    flash('Замовлення скасовано.', 'info')
    return redirect(url_for('profile'))


@app.route('/cancel_my_reservation/<int:res_id>', methods=['POST'])
@login_required
def cancel_my_reservation(res_id):
    res = Reservation.query.filter_by(id=res_id, user_id=current_user.id).first_or_404()
    db.session.delete(res)
    db.session.commit()
    flash('Бронювання скасовано.', 'info')
    return redirect(url_for('profile'))


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.is_admin:
        flash('Доступ заборонено.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        if 'add_category' in request.form:
            cat_name = request.form.get('category_name')
            if cat_name and not Category.query.filter_by(name=cat_name).first():
                db.session.add(Category(name=cat_name))
                db.session.commit()
                flash('Категорію додано.', 'success')

        elif 'delete_category' in request.form:
            cat_id = request.form.get('category_id')
            cat = Category.query.get(cat_id)
            if cat:
                db.session.delete(cat)
                db.session.commit()
                flash('Категорію видалено.', 'info')

        elif 'add_dish' in request.form:
            title = request.form.get('title')
            category_id = request.form.get('category_id')
            price = float(request.form.get('price'))
            description = request.form.get('description')
            full_description = request.form.get('full_description')
            file = request.files.get('image')

            filename = 'default.jpg'
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            dish = Dish(
                title=title,
                category_id=category_id,
                price=price,
                description=description,
                full_description=full_description,
                image=filename
            )
            db.session.add(dish)
            db.session.commit()
            flash('Страву додано.', 'success')

        elif 'grant_admin' in request.form and current_user.is_superadmin:
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_admin = True
                db.session.commit()
                flash(f'Користувача {user.username} призначено адміном.', 'success')
            else:
                flash('Користувача не знайдено.', 'danger')

        return redirect(url_for('admin'))

    categories = Category.query.all()
    dishes = Dish.query.all()
    reservations = Reservation.query.all()
    active_orders = Order.query.filter_by(status='В обробці').order_by(Order.created_at.desc()).all()
    completed_orders = Order.query.filter_by(status='Виконано').order_by(Order.created_at.desc()).all()
    admins = User.query.filter_by(is_admin=True).all()

    return render_template('admin.html', categories=categories, dishes=dishes, reservations=reservations,
                           active_orders=active_orders, completed_orders=completed_orders, admins=admins,
                           is_super_admin=current_user.is_superadmin)


@app.route('/complete_order/<int:order_id>', methods=['POST'])
@login_required
def complete_order(order_id):
    if not current_user.is_admin:
        flash('Доступ заборонено.', 'danger')
        return redirect(url_for('index'))
    order = Order.query.get_or_404(order_id)
    order.status = 'Виконано'
    db.session.commit()
    flash(f'Замовлення №{order.id} позначено як виконане!', 'success')
    return redirect(url_for('admin'))


@app.route('/edit_dish/<int:dish_id>', methods=['GET', 'POST'])
@login_required
def edit_dish(dish_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    dish = Dish.query.get_or_404(dish_id)
    if request.method == 'POST':
        dish.title = request.form.get('title')
        dish.category_id = request.form.get('category_id')
        dish.price = float(request.form.get('price'))
        dish.description = request.form.get('description')
        dish.full_description = request.form.get('full_description')

        file = request.files.get('image')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            dish.image = filename

        db.session.commit()
        flash('Страву оновлено.', 'success')
        return redirect(url_for('admin'))

    categories = Category.query.all()
    return render_template('edit_dish.html', dish=dish, categories=categories)


@app.route('/delete_dish/<int:dish_id>', methods=['POST'])
@login_required
def delete_dish(dish_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    dish = Dish.query.get_or_404(dish_id)
    db.session.delete(dish)
    db.session.commit()
    flash('Страву видалено.', 'info')
    return redirect(url_for('admin'))


@app.route('/cancel_reservation/<int:res_id>', methods=['POST'])
@login_required
def cancel_reservation(res_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    res = Reservation.query.get_or_404(res_id)
    db.session.delete(res)
    db.session.commit()
    flash('Бронювання скасовано.', 'info')
    return redirect(url_for('admin'))


@app.route('/revoke_admin/<int:user_id>', methods=['POST'])
@login_required
def revoke_admin(user_id):
    if not current_user.is_superadmin:
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    if not user.is_superadmin:
        user.is_admin = False
        db.session.commit()
        flash('Права адміністратора відкликано.', 'info')
    return redirect(url_for('admin'))


with app.app_context():
    db.create_all()

    if Category.query.count() < 4:
        c_h = Category(name='Хачапурі')
        c_g = Category(name='Гарячі страви')
        c_v = Category(name='Вина')
        c_n = Category(name='Напої')
        db.session.add_all([c_h, c_g, c_v, c_n])
        db.session.commit()

    if Dish.query.count() < 12:
        c_h = Category.query.filter_by(name='Хачапурі').first()
        c_g = Category.query.filter_by(name='Гарячі страви').first()
        c_v = Category.query.filter_by(name='Вина').first()
        c_n = Category.query.filter_by(name='Напої').first()

        if c_h and c_g and c_v and c_n:
            sample_dishes = [
                Dish(title='Хачапурі по-аджарськи', category_id=c_h.id, price=220.0,
                     description='Класичний човник із сиром сулугуні.',
                     full_description='Класичний човник із сиром сулугуні, вершковим маслом та сирим жовтком. Випікається у дров’яній печі до золотистої скоринки.',
                     image='default1.jpg'),
                Dish(title='Хачапурі по-мегрельськи', category_id=c_h.id, price=240.0,
                     description='Запечений круглий коржик із сиром.',
                     full_description='Запечений круглий коржик із подвійною порцією сиру сулугуні. Надзвичайно ситно та смачно.',
                     image='default2.jpg'),
                Dish(title='Хачапурі по-імператорськи', category_id=c_h.id, price=210.0,
                     description='Елітна випічка з трьома видами сиру.',
                     full_description='Елітна випічка з трьома видами сиру та трьома відбірними жовтками.',
                     image='default3.jpg'),
                Dish(title='Кубдарі', category_id=c_h.id, price=260.0,
                     description='Грузинський пиріг із соковитим м’ясом.',
                     full_description='Грузинський пиріг із соковитим рубленим м’ясом свинини та яловичини зі спеціями.',
                     image='default4.jpg'),
                Dish(title='Хінкалі з яловичиною (5 шт)', category_id=c_g.id, price=190.0,
                     description='Соковиті хінкалі з м’ясним фаршем.',
                     full_description='Традиційні соковиті хінкалі з духмяним м’ясним фаршем та свіжою зеленню.',
                     image='default5.jpg'),
                Dish(title='Хінкалі з сиром (5 шт)', category_id=c_g.id, price=180.0,
                     description='Ніжні хінкалі з сулугуні.',
                     full_description='Ніжні хінкалі з начинкою з міксу сулугуні та імеретинського сиру.',
                     image='default5.jpg'),
                Dish(title='Оджахурі зі свининою', category_id=c_g.id, price=270.0,
                     description='Смажене м’ясо з картоплею.',
                     full_description='Смажене м’ясо з картоплею, цибулею, томатами та грузинськими спеціями.',
                     image='default5.jpg'),
                Dish(title='Чашушулі', category_id=c_g.id, price=250.0,
                     description='Тушкована телятина в томатному соусі.',
                     full_description='Ніжна телятина, тушкована в томатному соусі з болгарським перцем та зеленню.',
                     image='default5.jpg'),
                Dish(title='Сапераві (червоне сухе)', category_id=c_v.id, price=450.0,
                     description='Традиційне грузинське вино, 0.75 л.',
                     full_description='Традиційне грузинське червоне сухе вино з насиченим гранатовим кольором та багатим смаком.',
                     image='default6.jpg'),
                Dish(title='Цинандалі (біле сухе)', category_id=c_v.id, price=420.0,
                     description='Біле вино з фруктовим ароматом, 0.75 л.',
                     full_description='Класичне біле сухе вино з витонченим фруктово-квітковим ароматом та легкою приємною кислинкою.',
                     image='default7.jpg'),
                Dish(title='Лимонад Натахтарі (Тархун)', category_id=c_n.id, price=75.0,
                     description='Освіжаючий лимонад, 0.5 л.',
                     full_description='Культовий освіжаючий грузинський лимонад на основі найчистішої гірської води.',
                     image='default8.jpg'),
                Dish(title='Лимонад Натахтарі (Маракуя)', category_id=c_n.id, price=75.0,
                     description='Лимонад зі смаком Маракуї, 0.5 л.',
                     full_description='Екзотичний та неймовірно ароматний лимонад зі смаком маракуї, що чудово тамує спрагу.',
                     image='default9.jpg')
            ]
            db.session.add_all(sample_dishes)
            db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)