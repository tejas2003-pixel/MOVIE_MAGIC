from flask import Flask, render_template, request, redirect, url_for, session, flash
import hashlib
import boto3  # AWS SDK

# ---------------- AWS Configuration ----------------
AWS_REGION = 'us-east-1'
USERS_TABLE = 'movie_magic_user'
SERVICES_TABLE = 'movie_magic_server'
BOOKINGS_TABLE = 'movie_magic_booking'  # 🔸 Booking table added"
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:324037304857:movie_magic_topic"

dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
sns_client = boto3.client('sns', region_name=AWS_REGION)

users_table = dynamodb.Table(USERS_TABLE)
services_table = dynamodb.Table(SERVICES_TABLE)
bookings_table = dynamodb.Table(BOOKINGS_TABLE)  # 🔸 Reference added

# ---------------------------------------------------

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Dummy movie list with theatre details
MOVIES = [
    {
        'title': 'Kubera',
        'price': 250,
        'theatres': [
            {'name': 'Starlite-punjab', 'price': 250, 'timings': ['9:00 AM', '6:30 PM', '10:30 PM']},
            {'name': 'Carnival Cinemas IMAX- chennai', 'price': 240, 'timings': ['9:00 AM', '6:30 PM', '10:30 PM']}
        ]
    },
    {
        'title': 'DEVARA',
        'price': 280,
        'theatres': [
            {'name': 'Jazz Cinemas LUXE - tamilnadu', 'price': 280, 'timings': ['7:00 AM', '10:30 AM', '10:30 PM']},
            {'name': 'PVR Premiere - Manjeera Mall', 'price': 280, 'timings': ['4:00 AM', '11:30 AM', '10:30 PM']}
        ]
    },
    {
        'title': 'Animal',
        'price': 300,
        'theatres': [
            {'name': 'PVR Cinemas - M Cube Mall', 'price': 300, 'timings': ['3:00 AM', '12:30 AM', '11:30 PM']},
            {'name': 'Miraj Cinemas- RTC X Roads', 'price': 260, 'timings': ['5:00 AM', '11:30 AM', '11:00 PM']}
        ]
    },
    {
        'title': 'Eleven',
        'price': 220,
        'theatres': [
            {'name': 'PVR Cinemas-Bangalore', 'price': 220, 'timings': ['2:00 AM', '7:30 AM', '9:30 PM']},
            {'name': 'Cinepolis - Manjeera Mall', 'price': 230, 'timings': ['3:00 AM', '9:30 AM', '8:30 PM']}
        ]
    },
    {
        'title': 'Pushpa 2',
        'price': 260,
        'theatres': [
            {'name': 'PVR - Panjagutta', 'price': 260, 'timings': ['1:00 AM', '11:00 AM', '2:00 PM']},
            {'name': 'Asian - Uppal', 'price': 250, 'timings': ['8:00 AM', '12:00 PM', '3:00 PM']}
        ]
    },
    {
        'title': 'Kalki',
        'price': 300,
        'theatres': [
            {'name': 'INOX - GVK One', 'price': 300, 'timings': ['9:00 AM', '1:00 PM', '6:00 PM']},
            {'name': 'Cinepolis - Hyderabad Central', 'price': 280, 'timings': ['10:00 AM', '2:00 PM', '7:00 PM']}
        ]
    },
]


users = {}

@app.route('/')
def index_html():
    return render_template('index.html')

@app.route('/home')
def home():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('home.html', movies=MOVIES)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        users[email] = {'name': name, 'password': password}
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = hashlib.sha256(request.form['password'].encode()).hexdigest()
        user = users.get(email)
        if user and user['password'] == password:
            session['email'] = email
            session['bookings'] = []
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully')
    return render_template('index.html')

@app.route('/booking', methods=['GET', 'POST'])
@app.route('/booking/<title>', methods=['GET', 'POST'])
def booking(title=None):
    if 'email' not in session:
        return redirect(url_for('login'))

    if not title:
        title = request.args.get('title')

    if not title:
        flash('Movie title is missing.')
        return redirect(url_for('home'))

    movie = next((m for m in MOVIES if m['title'].upper() == title.upper()), None)

    if not movie:
        flash('Movie not found.')
        return redirect(url_for('home'))

    if request.method == 'POST':
        show_time = request.form.get('show_time')
        if not show_time:
            flash('Please select a show time.')
            return render_template('booking.html', movie=movie)
        return redirect(url_for('seating', title=title, show_time=show_time))

    return render_template('booking.html', movie=movie)

@app.route('/seating/<title>', methods=['GET', 'POST'])
def seating(title):
    if 'email' not in session:
        return redirect(url_for('login'))

    movie = next((m for m in MOVIES if m['title'].upper() == title.upper()), None)
    if not movie:
        flash('Movie not found')
        return redirect(url_for('home'))

    if request.method == 'POST':
        seats_raw = request.form.get('seats')
        if not seats_raw:
            flash('No seats selected.')
            return redirect(url_for('seating', title=title))

        selected_seats = seats_raw.split(',')

        total = 0
        seat_list = []
        prices = []

        for seat in selected_seats:
            if ':' not in seat:
                continue
            seat_name, seat_type = seat.split(':')
            seat_list.append(seat_name)

            if seat_type == 'premium':
                price = 250
            elif seat_type == 'gold':
                price = 170
            else:
                flash(f"Unknown seat type: {seat_type}")
                return redirect(url_for('seating', title=title))

            total += price
            prices.append(price)

        price_per_ticket = prices[0] if prices else 0

        booking = {
            'movie': movie['title'],
            'seats': ', '.join(seat_list),
            'price': price_per_ticket,
            'total': total
        }

        # Instead of saving booking and redirecting to tickets, redirect to payment
        return redirect(url_for('payment', title=title, seats=','.join(seat_list), total=total))

    return render_template('seating.html', movie=movie)

@app.route('/payment/<title>', methods=['GET', 'POST'])
def payment(title):
    if 'email' not in session:
        return redirect(url_for('login'))
    
    seats = request.args.get('seats', '')
    total = request.args.get('total', 0)
    
    return render_template('payment.html', movie=title, seats=seats, total=total)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    # Get form data
    movie = request.form.get('movie')
    seats = request.form.get('seats')
    total = request.form.get('total')
    payment_method = request.form.get('payment_method')
    
    # Process the payment (in a real app, you would integrate with a payment gateway)
    # For this demo, we'll just assume the payment was successful
    
    # Create a booking record
    seat_list = [s.split(':')[0] if ':' in s else s for s in seats.split(',')]
    
    booking = {
        'movie': movie,
        'seats': ', '.join(seat_list),
        'payment_method': payment_method,
        'total': total
    }
    
    session.setdefault('bookings', []).append(booking)
    session.modified = True
    
    # Optional: Send confirmation via SNS
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=f"Booking Confirmed for {movie} - Seats: {seat_list}",
            Subject="Movie Booking Confirmation"
        )
    except Exception as e:
        print("SNS publish failed:", e)
    
    # Print debug information
    print(f"Processing payment for {movie}, seats: {seats}, total: {total}, method: {payment_method}")
    
    # Flash success message
    flash('Payment successful! Your tickets are ready.')
    
    # Redirect to the tickets page
    return redirect(url_for('tickets', title=movie, seats=seats, total=total))

@app.route('/tickets')
def tickets():
    title = request.args.get('title')
    seats_raw = request.args.get('seats', '')
    total = request.args.get('total', 0)
    
    # If total is not provided in the URL, calculate it
    if not total:
        seat_list = [s.strip() for s in seats_raw.split(',') if s.strip()]
        total = 0
        for seat in seat_list:
            if ':' in seat:
                seat_num, category = seat.split(':')
                if category == 'premium':
                    total += 250
                elif category == 'gold':
                    total += 170
            else:
                total += 200

    return render_template('tickets.html', title=title, seats=", ".join([s.split(':')[0] if ':' in s else s for s in seats_raw.split(',')]), total=total)

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))

    bookings = session.get('bookings', [])
    return render_template('dashboard.html', bookings=bookings)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        # Here you can process the form data (e.g., save to database, send email)
        flash('Thank you for contacting us! We will get back to you soon.')
        return redirect(url_for('contact'))
    return render_template('contact.html')

# ---------------- For EC2 ----------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
