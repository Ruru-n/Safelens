from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash
import config
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DISCOVERY_URL
import psycopg2
import calendar
import re
from functools import wraps
from flask import make_response




EMAIL_REGEX = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'  # strict pattern


app = Flask(__name__)


app.config.from_object('config')
app.secret_key = "safelens_secret_key"


mail = Mail(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])


oauth = OAuth(app)


#para sa continue with google
google = oauth.register(
   name='google',
   client_id=GOOGLE_CLIENT_ID,
   client_secret=GOOGLE_CLIENT_SECRET,
   server_metadata_url=GOOGLE_DISCOVERY_URL,
   client_kwargs={
       'scope': 'openid email profile'
   }
)


# PostgreSQL connection parameters
DB_HOST = "localhost"
DB_NAME = "safelens"
DB_USER = "jonathanbagusto"


def get_db_connection():
   conn = psycopg2.connect(
       host=DB_HOST,
       dbname=DB_NAME,
       user=DB_USER,
   )
   return conn


#----------------------------------------
# Helper functions for /allCrimeTrend YUNG VIEW ALL
#----------------------------------------


def get_all_months_for_year(year):
   """Return all months in proper order."""
   return ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def get_crime_cases_per_month(year):
   """Return list of number of crime cases per month in order."""
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("""
       SELECT "Month", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Month"
   """, (year,))
   rows = cur.fetchall()
   cur.close()
   conn.close()


   # Build dict month_name → cases
   month_dict = {row[0].strip().title(): row[1] for row in rows}


   # Fill missing months with 0 and preserve order
   months_order = get_all_months_for_year(year)
   cases = [month_dict.get(m, 0) for m in months_order]
   return cases


def generate_crime_trend_analysis(year):
   """Optional: simple textual analysis."""
   cases = get_crime_cases_per_month(year)
   months = get_all_months_for_year(year)
   if max(cases) == 0:
       return f"No crime data available for {year}."
   peak_index = cases.index(max(cases))
   return f"Highest crime recorded in {months[peak_index]} with {cases[peak_index]} cases."




#GOOGLE LOGIN ROUTE
@app.route("/login/google")
def login_google():
   redirect_uri = url_for('auth_google_callback', _external=True)
   return google.authorize_redirect(redirect_uri)


#GOOGLE CALLBACK ROUTE
@app.route("/auth/google/callback")
def auth_google_callback():
   token = google.authorize_access_token()
   user_info = google.parse_id_token(token)


   # Extract info
   email = user_info.get('email')
   google_id = user_info.get('sub')  # unique Google user ID


   conn = get_db_connection()
   cur = conn.cursor()


   # Check if user exists
   cur.execute("SELECT id FROM users WHERE email = %s", (email,))
   user = cur.fetchone()


   if not user:
       # Insert new user with Google auth
       cur.execute(
           "INSERT INTO users (email, auth_provider, provider_user_id) VALUES (%s, %s, %s) RETURNING id",
           (email, 'google', google_id)
       )
       user_id = cur.fetchone()[0]
       conn.commit()
   else:
       user_id = user[0]


   cur.close()
   conn.close()


   # Set session
   session['user_id'] = user_id
   session['email'] = email


   return redirect(url_for('lensHome'))


#API ENDPOINT SA SUMMARY DATA SA HOMEPAGE
@app.route("/lensHomeData")
def lensHomeData():
   year = request.args.get('year', '2025')


   conn = get_db_connection()
   cur = conn.cursor()


   # Top Municipality
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS total_cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY total_cases DESC
       LIMIT 1
   """, (year,))
   municipality = cur.fetchone()
   municipality_name = municipality[0] if municipality else "-"
   municipality_cases = municipality[1] if municipality else 0


   # Most Common Crime
   cur.execute("""
       SELECT "Crime_Type", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       AND "Crime_Type" != 'Others'
       GROUP BY "Crime_Type"
       ORDER BY cases DESC
       LIMIT 1;
   """, (year,))
   crime = cur.fetchone()
   crime_type = crime[0] if crime else "-"
   crime_cases = crime[1] if crime else 0


   # Peak Month
   cur.execute("""
       SELECT "Month", COUNT(*) AS total_cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Month"
       ORDER BY total_cases DESC
       LIMIT 1
   """, (year,))
   month = cur.fetchone()
   month_name = month[0] if month else "-"
   month_cases = month[1] if month else 0


   # Total Cases
   cur.execute("""
       SELECT COUNT(*)
       FROM crime_reports
       WHERE "Year" = %s
   """, (year,))
   total_cases = cur.fetchone()[0]


   cur.close()
   conn.close()


   return jsonify({
       "municipality": {
           "name": municipality_name,
           "cases": municipality_cases
       },
       "crime": {
           "type": crime_type,
           "cases": crime_cases
       },
       "peak_month": {
           "name": month_name,
           "cases": month_cases
       },
       "total_cases": total_cases
   })


#WELCOME PAGE BEFORE MAG-LOGIN OR REGISTER
@app.route("/login")
def login():
   return render_template("login.html")


#MAG-LOGIN
# @app.route("/userLogin", methods=['GET', 'POST'])
# def userLogin():
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']


#         conn = get_db_connection()
#         cur = conn.cursor()


#         # Fetch user by email
#         cur.execute("""
#             SELECT id, email, password_hash, auth_provider
#             FROM users
#             WHERE email = %s
#         """, (email,))


#         user = cur.fetchone()
#         cur.close()
#         conn.close()


#         if user:
#             user_id, user_email, user_password_hash, auth_provider = user


#             if auth_provider == "google":
#                 flash("This email is registered using Google Sign-In.", "password_error")
#                 return render_template("userLogin.html")


#             if check_password_hash(user_password_hash, password):
#                 session['user_id'] = user_id
#                 session['email'] = user_email
#                 return redirect(url_for('lensHome'))
#             else:
#                 flash('Incorrect password. Please try again.', 'password_error')
#         else:
#             flash('Email not found. Please check your email.', 'email_error')
          
#         if check_password_hash(user_password_hash, password):
#             session['user_id'] = user_id
#             session['email'] = user_email
          
#             # Set default municipality and year if not already in session
#             if 'municipality' not in session:
#                 session['municipality'] = "Default Municipality"  # replace with a real default
#             if 'year' not in session:
#                 session['year'] = 2025


#             return redirect(url_for('userMap'))  # or lensHome, depending on your flow


#     # GET request or failed login
#     return render_template("userLogin.html")


# USER LOGIN
@app.route("/userLogin", methods=['GET', 'POST'])
def userLogin():
   if request.method == 'POST':
       email = request.form['email'].strip()
       password = request.form['password'].strip()


       conn = get_db_connection()
       cur = conn.cursor()


       # Fetch user by email
       cur.execute("""
           SELECT id, email, password_hash, auth_provider, municipality
           FROM users
           WHERE email = %s
       """, (email,))


       user = cur.fetchone()
       cur.close()
       conn.close()


       if not user:
           flash('Email not found. Please check your email.', 'email_error')
           return render_template("userLogin.html")


       user_id, user_email, user_password_hash, auth_provider, user_muni = user


       # If registered via Google
       if auth_provider == "google":
           flash("This email is registered using Google Sign-In.", "password_error")
           return render_template("userLogin.html")


       # Check password
       if not check_password_hash(user_password_hash, password):
           flash('Incorrect password. Please try again.', 'password_error')
           return render_template("userLogin.html")


       # Login successful
       session['user_id'] = user_id
       session['email'] = user_email


       # ✅ Use the existing municipality from the DB as default
       session['municipality'] = user_muni or "Default Municipality"  # fallback just in case
       session['year'] = 2025  # or last used year if stored in DB


       return redirect(url_for('lensHome'))  # or lensHome depending on your flow


   return render_template("userLogin.html")




#REGISTER ACCOUNT
# @app.route("/userSignIn", methods=['GET', 'POST'])
# def userSignIn():
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
      
#         # --- SERVER-SIDE EMAIL VALIDATION ---
#         if not re.match(EMAIL_REGEX, email):
#             flash("Please enter a valid email address.", "error")
#             return redirect(url_for('userSignIn'))
      
#         # Additional check: email must have a dot (.) after @
#         if '.' not in email.split('@')[-1]:
#             flash("Please enter a valid email address with a domain.", "error")
#             return redirect(url_for('userSignIn'))
      
#         valid_tlds = ['com', 'org', 'net', 'gov', 'edu', 'ph']
#         domain_tld = email.split('.')[-1].lower()
#         if domain_tld not in valid_tlds:
#             flash("Email must end with a valid domain like .com, .org, .ph", "error")
#             return redirect(url_for('userSignIn'))


#         # --- PASSWORD VALIDATION ---
#         if len(password) < 8:
#             flash("Password must be at least 8 characters.", "error")
#             return redirect(url_for('userSignIn'))


#         hashed_password = generate_password_hash(password)


#         conn = get_db_connection()
#         cur = conn.cursor()


#         # Check if email already exists
#         cur.execute("SELECT id FROM users WHERE email = %s", (email,))
#         if cur.fetchone():  # simpler
#             flash("Email already registered. Try logging in.", "error")
#             cur.close()
#             conn.close()
#             return redirect(url_for('userSignIn'))


#         # Insert new user
#         cur.execute(
#             """
#             INSERT INTO users (email, password_hash, auth_provider)
#             VALUES (%s, %s, 'local')
#             RETURNING id
#             """,
#             (email, hashed_password)
#         )


#         user_id = cur.fetchone()[0]  # ✅ Kunin ang bagong user id
#         conn.commit()
#         cur.close()
#         conn.close()
      
#         # Automatic login: set session
#          # Automatic login: set session
#         session['user_id'] = user_id
#         session['email'] = email


#         # Redirect sa last welcome page
#         return redirect(url_for('lastWelcome'))


#     return render_template("userSignIn.html")


# REGISTER ACCOUNT
@app.route("/userSignIn", methods=['GET', 'POST'])
def userSignIn():
   if request.method == 'POST':
       email = request.form['email'].strip()
       password = request.form['password'].strip()
      
       # --- EMAIL VALIDATION ---
       if not re.match(EMAIL_REGEX, email):
           flash("Please enter a valid email address.", "error")
           return redirect(url_for('userSignIn'))


       # Additional domain check
       if '.' not in email.split('@')[-1]:
           flash("Please enter a valid email address with a domain.", "error")
           return redirect(url_for('userSignIn'))
      
       valid_tlds = ['com', 'org', 'net', 'gov', 'edu', 'ph']
       domain_tld = email.split('.')[-1].lower()
       if domain_tld not in valid_tlds:
           flash("Email must end with a valid domain like .com, .org, .ph", "error")
           return redirect(url_for('userSignIn'))


       # --- PASSWORD VALIDATION ---
       if len(password) < 8:
           flash("Password must be at least 8 characters.", "error")
           return redirect(url_for('userSignIn'))


       hashed_password = generate_password_hash(password)


       conn = get_db_connection()
       cur = conn.cursor()


       # Check if email already exists
       cur.execute("SELECT id FROM users WHERE email = %s", (email,))
       if cur.fetchone():
           flash("Email already registered. Try logging in.", "error")
           cur.close()
           conn.close()
           return redirect(url_for('userSignIn'))


       # Insert new user
       cur.execute(
           """
           INSERT INTO users (email, password_hash, auth_provider)
           VALUES (%s, %s, 'local')
           RETURNING id
           """,
           (email, hashed_password)
       )


       user_id = cur.fetchone()[0]
       conn.commit()
       cur.close()
       conn.close()
      
       # Automatic login
       session['user_id'] = user_id
       session['email'] = email


       return redirect(url_for('selectMuni'))


   return render_template("userSignIn.html")




#FORGOT PASSWORD
@app.route('/forgot-password', methods=['POST'])
def forgot_password():
   email = request.json.get('email')


   conn = get_db_connection()
   cur = conn.cursor()
  
   cur.execute("SELECT id FROM users WHERE email = %s", (email,))
   user = cur.fetchone()


   if not user:
       return {"status": "success", "message": "If the email exists, a reset link was sent."}


   token = serializer.dumps(email, salt='password-reset')


   reset_link = url_for('reset_password', token=token, _external=True)


   msg = Message(
       subject="Password Reset Request",
       recipients=[email],
       body=f"""Hello,
       Click the link below to reset your password:
       {reset_link}
       This link will expire in 15 minutes.
       If you didn't request this, please ignore this email.
       """
           )


   mail.send(msg)


   return {"status": "success", "message": "Reset link sent to your email."}


#RESET PASSWORD
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
   try:
       email = serializer.loads(token, salt='password-reset', max_age=900)
   except:
       return "The reset link is invalid or expired."


   if request.method == 'POST':
       new_password = request.form['password']
       hashed = generate_password_hash(new_password)


       conn = get_db_connection()
       cur = conn.cursor()
       cur.execute(
           "UPDATE users SET password_hash = %s WHERE email = %s",
           (hashed, email)
       )
       conn.commit()


       return redirect(url_for('userLogin'))


   return render_template('reset_password.html')


#WELCOME PAGE AFTER REGISTRATION
@app.route("/firstWelcome")
def firstWelcome():
   return render_template("firstWelcome.html")
  
#HOMEPAGE
@app.route("/lensHome")
def lensHome():
   year = request.args.get('year', '2025')


   conn = get_db_connection()
   cur = conn.cursor()
  


   # Municipality with highest crime rate
   cur.execute("""
       SELECT "Municipality", COUNT(*) as total_cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY total_cases DESC
       LIMIT 1
   """, (year,))
   municipality_data = cur.fetchone()   # (Municipality, total_cases) top municipality




   # -----------------------------------------
   # 2️⃣ Most common crime type
   # -----------------------------------------
   cur.execute("""
       SELECT "Crime_Type", COUNT(*) as total_cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Crime_Type"
       ORDER BY total_cases DESC
       LIMIT 1
   """, (year,))
   crime_data = cur.fetchone()           # (Type_of_crime, total_cases) most common crime type




   # -----------------------------------------
   # 3️⃣ Peak month (highest number of crimes)
   # -----------------------------------------
   cur.execute("""
       SELECT "Month", COUNT(*) as total_cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Month"
       ORDER BY total_cases DESC
       LIMIT 1
   """, (year,))
   month_data = cur.fetchone()           # (MonthNumber, total_cases) peak month
  
   # 4️⃣ Total Crime Cases in that year
   cur.execute("""
       SELECT COUNT(*)
       FROM crime_reports
       WHERE "Year" = %s
       """, (year,))
   total_cases = cur.fetchone()[0]




   cur.close()
   conn.close()


   # Unpack the peak month data: month_name is the month (text), month_cases is the number of cases.
   # If month_data is None (no records for the year), default to None and 0.
   month_name, month_cases = month_data if month_data else (None, 0)
  
   # -----------------------------------------
   # Send EVERYTHING to template
   # -----------------------------------------


   return render_template(
       "lensHome.html",
       year=year,
       municipality_data=municipality_data,
       crime_data=crime_data,
       month_name=month_name,
       month_cases=month_cases,
       total_cases=total_cases,
       active_page="home"
   )
  


@app.route("/secondWelcome")
def secondWelcome():
   return render_template("secondWelcome.html")


@app.route("/thirdWelcome")
def thirdWelcome():
   return render_template("thirdWelcome.html")


@app.route("/fourthWelcome")
def fourthWelcome():
   return render_template("fourthWelcome.html")


@app.route("/fifthWelcome")
def fifthWelcome():
   return render_template("fifthWelcome.html")


@app.route("/selectMuni")
def selectMuni():
   return render_template("selectMuni.html")


@app.route("/lensHome2")
def tryulit():
   return render_template("lensHome2.html")




#FULL ANALYTICS
@app.route("/lensAnalytics")
def analytics():
   year = int(request.args.get("year", 2025))
  
   conn = get_db_connection()
   cur = conn.cursor()


   # YEARS FOR DROPDOWN
   cur.execute("""
       SELECT DISTINCT "Year"
       FROM crime_reports
       ORDER BY "Year" DESC
   """)
   years = [row[0] for row in cur.fetchall()]
  
   if not year or int(year) not in years:
       year = years[0]
      
   # 🔹 Total cases per year (whole Pangasinan)
   cur.execute("""
       SELECT COUNT(*)
       FROM crime_reports
       WHERE "Year" = %s
   """, (year,))
   total_cases = cur.fetchone()[0]
  
   # 🔹 Monthly peak (highest crime month of the year)
   cur.execute("""
       SELECT "Month", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Month"
       ORDER BY cases DESC
       LIMIT 1
   """, (year,))


   peak_row = cur.fetchone()
   peak_month, peak_month_cases = peak_row if peak_row else ("-", 0)
  
   # Monthly trend for the whole Pangasinan
   cur.execute("""
       SELECT "Month", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Month"
       ORDER BY "Month" ASC
   """, (year,))
   trend_rows = cur.fetchall()


   # Standard month order
   months_order = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]


   # Make a clean dictionary from query
   month_dict = {}
   for row in trend_rows:
       month_name = row[0].strip().title()  # ensures "january" → "January"
       month_cases = row[1]
       month_dict[month_name] = month_cases


   # Fill missing months with 0 and preserve order
   months = []
   cases = []
   for m in months_order:
       months.append(m)
       cases.append(month_dict.get(m, 0))


   # 🔹 Top 3 municipalities (for mini card)
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY cases DESC
       LIMIT 3
   """, (year,))
   top3_munis = cur.fetchall()  # [(Mun1, cases), (Mun2, cases), (Mun3, cases)]
   top3_labels = [row[0] for row in top3_munis]
   top3_values = [row[1] for row in top3_munis]
  
       # 🔹 All municipalities (View All)
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY cases DESC
   """, (year,))
   all_munis = cur.fetchall()
   all_labels = [row[0] for row in all_munis]
   all_values = [row[1] for row in all_munis]




   # 🔹 Top Municipality overall (total cases, filtered by year)
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY cases DESC
       LIMIT 1;
   """, (year,))
   top_muni_row = cur.fetchone()
   top_municipality, top_municipality_cases = top_muni_row if top_muni_row else ("-", 0)


   # 🔹 Most Common Crime Type overall (filtered by year)
   cur.execute("""
       SELECT "Crime_Type", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       AND "Crime_Type" != 'Others'
       GROUP BY "Crime_Type"
       ORDER BY cases DESC
       LIMIT 1;
   """, (year,))
   common_crime_row = cur.fetchone()
   if common_crime_row:
       common_crime, common_crime_cases = common_crime_row
   else:
       common_crime, common_crime_cases = "-", 0


   # 🔹 Table: Top Municipality per Crime Type (exclude 'Others')
   cur.execute("""
       SELECT crime, municipality, cases FROM (
           SELECT
               "Crime_Type" AS crime,
               "Municipality" AS municipality,
               COUNT(*) AS cases,
               ROW_NUMBER() OVER(PARTITION BY "Crime_Type" ORDER BY COUNT(*) DESC) AS rn
           FROM crime_reports
           WHERE "Year" = %s
           AND "Crime_Type" != 'Others'
           GROUP BY "Crime_Type", "Municipality"
       ) t
       WHERE rn = 1
       ORDER BY
           CASE crime
               WHEN 'Robbery' THEN 1
               WHEN 'Vandalism' THEN 2
               WHEN 'Drugs' THEN 3
               WHEN 'Rape' THEN 4
               WHEN 'Abuse' THEN 5
               WHEN 'Theft' THEN 6
               WHEN 'Homicide' THEN 7
               ELSE 8
           END;
   """, (year,))


   table_data = [
       {"crime": row[0], "municipality": row[1], "cases": row[2]}
       for row in cur.fetchall()
   ]


   cur.close()
   conn.close()


   return render_template(
       "lensAnalytics.html",
       total_cases=total_cases,
       years=years,
       selected_year=int(year),
       top_municipality=top_municipality,
       top_municipality_cases=top_municipality_cases,
       common_crime=common_crime,
       table_data=table_data,
       peak_month=peak_month,
       peak_month_cases=peak_month_cases,
       common_crime_cases=common_crime_cases,
       trend_months=months,
       trend_cases=cases,
       municipality_names=top3_labels,   # ✅ top 3 municipalities for initial chart
       municipality_cases=top3_values,   # ✅ initial values
       all_municipality_names=all_labels,  # ✅ all municipalities for "View All"
       all_municipality_cases=all_values,
       active_page="analytics"
   )
  
#for user
@app.route("/allCrimeTrend")
def allCrimeTrend():
   year = request.args.get('year', 2025)  # default 2025
   # Kunin lahat ng monthly crime data para sa selected year
   trend_months = get_all_months_for_year(year)  # list ng buwan
   trend_cases = get_crime_cases_per_month(year)  # list ng cases per month


   # Text analysis (maaaring summary o insights)
   analysis_text = generate_crime_trend_analysis(year) 


   return render_template("allCrimeTrend.html",
                          year=year,
                          trend_months=trend_months,
                          trend_cases=trend_cases,
                          analysis_text=analysis_text)
  
#for guest
@app.route("/allCrimeTrendGuest")
def allCrimeTrendGuest():
   year = request.args.get('year', 2025)  # default 2025
   # Kunin lahat ng monthly crime data para sa selected year
   trend_months = get_all_months_for_year(year)  # list ng buwan
   trend_cases = get_crime_cases_per_month(year)  # list ng cases per month


   # Text analysis (maaaring summary o insights)
   analysis_text = generate_crime_trend_analysis(year) 


   return render_template("allCrimeTrendGuest.html",
                          year=year,
                          trend_months=trend_months,
                          trend_cases=trend_cases,
                          analysis_text=analysis_text)
  




  
#SAVE MUNICIPALITY, MAGAGAMIT SA DEFAULT CARD SA MAY MAP
@app.route("/save_municipality", methods=["POST"])
def save_municipality():
   # Siguraduhin naka-login
   user_id = session.get('user_id')
   if not user_id:
       return jsonify({"success": False, "message": "User not logged in"}), 401


   data = request.get_json()
   municipality = data.get("municipality")


   if not municipality:
       return jsonify({"success": False, "message": "No municipality provided"}), 400


   # Update sa database
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute(
       "UPDATE users SET municipality = %s WHERE id = %s",
       (municipality, user_id)
   )
   conn.commit()
   cur.close()
   conn.close()
  
   # ✅ Store municipality sa session para magamit sa analytics
   session['municipality'] = municipality


   return jsonify({"success": True})


#for user
@app.route("/allMunicipalities")
def allMunicipalities():
   year = request.args.get("year", 2025)


   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY cases DESC
   """, (year,))
   all_munis = cur.fetchall()
   cur.close()
   conn.close()


   return render_template("allMunicipalities.html",
                          municipalities=all_munis,
                          year=year,
                          active_page="analytics")
  
#for guest
@app.route("/allMunicipalitiesGuest")
def allMunicipalitiesGuest():
   year = request.args.get("year", 2025)


   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY cases DESC
   """, (year,))
   all_munis = cur.fetchall()
   cur.close()
   conn.close()


   return render_template("allMunicipalitiesGuest.html",
                          municipalities=all_munis,
                          year=year,
                          active_page="analytics")
  
  
# #old route icomment out muna
@app.route('/searchMunicipality')
def search_municipality():
   name = request.args.get('name', '').strip()
   year = request.args.get('year')


   if not name:
       return jsonify({"error": "No municipality provided"}), 400


   try:
       year = int(year) if year else 2025
   except ValueError:
       return jsonify({"error": "Invalid year"}), 400


   conn = get_db_connection()
   cur = conn.cursor()


   # TOTAL CASES with case-insensitive search
   cur.execute("""
       SELECT COUNT(*), MIN("Municipality")
       FROM crime_reports
       WHERE "Municipality" ILIKE %s AND "Year" = %s
   """, (name, year))
   result = cur.fetchone()
   total_cases = result[0]
   proper_name = result[1]  # will give the correctly cased name from DB
  
   if total_cases == 0:
       # Municipality not found for that year
       cur.close()
       conn.close()
       return jsonify({"error": "Municipality not found"})


   # TOP CRIME
   cur.execute("""
       SELECT "Crime_Type", COUNT(*)
       FROM crime_reports
       WHERE "Municipality" = %s AND "Year" = %s
       GROUP BY "Crime_Type"
       ORDER BY COUNT(*) DESC
       LIMIT 1
   """, (name, year))
   crime = cur.fetchone()


   # PEAK MONTH
   cur.execute("""
       SELECT "Month", COUNT(*)
       FROM crime_reports
       WHERE "Municipality" = %s AND "Year" = %s
       GROUP BY "Month"
       ORDER BY COUNT(*) DESC
       LIMIT 1
   """, (name, year))
   peak = cur.fetchone()


   cur.close()
   conn.close()


   return jsonify({
       "municipality": {
           "name": proper_name,
           "cases": total_cases
       },
       "crime": {
           "type": crime[0] if crime else "-",
           "cases": crime[1] if crime else 0
       },
       "peak_month": {
           "name": peak[0] if peak else "-",
           "cases": peak[1] if peak else 0
       },
       "year": year
   })
  
  
# #search suggestions
# @app.route('/municipalitySuggestions')
# def municipality_suggestions():
#     query = request.args.get('q', '').strip()
#     if not query:
#         return jsonify([])


#     conn = get_db_connection()
#     cur = conn.cursor()
#     cur.execute("""
#         SELECT DISTINCT "Municipality"
#         FROM crime_reports
#         WHERE "Municipality" ILIKE %s
#         ORDER BY "Municipality" ASC
#         LIMIT 5
#     """, (query + '%',))
#     results = [row[0] for row in cur.fetchall()]
#     cur.close()
#     conn.close()
#     return jsonify(results)




  
@app.route('/editProfile')
def editProfile():
   return render_template('editProfile.html')


@app.route('/security')
def security():
   return render_template('security.html')


#change password
@app.route('/change-password', methods=['POST'])
def change_password():
   user_id = session.get('user_id')
   if not user_id:
       flash("You must be logged in to change your password.", "error")
       return redirect(url_for('login'))


   # Get form values
   current_password = request.form.get("current_password")
   new_password = request.form.get("new_password")
   confirm_password = request.form.get("confirm_password")


   # Validation
   if not current_password or not new_password or not confirm_password:
       flash("All fields are required.", "error")
       return redirect(url_for('security'))


   if new_password != confirm_password:
       flash("New password and confirmation do not match.", "error")
       return redirect(url_for('security'))


   if len(new_password) < 8:
       flash("New password must be at least 8 characters.", "error")
       return redirect(url_for('security'))


   # Fetch current password hash
   conn = get_db_connection()
   cur = conn.cursor()
   cur.execute("SELECT password_hash FROM users WHERE id = %s AND auth_provider = 'local'", (user_id,))
   user = cur.fetchone()


   if not user:
       cur.close()
       conn.close()
       flash("Cannot change password for this account.", "error")
       return redirect(url_for('security'))


   password_hash = user[0]


   if not check_password_hash(password_hash, current_password):
       cur.close()
       conn.close()
       flash("Current password is incorrect.", "error")
       return redirect(url_for('security'))


   # Update password
   new_hash = generate_password_hash(new_password)
   cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
   conn.commit()
   cur.close()
   conn.close()


   flash("Password updated successfully!", "success")
   return redirect(url_for('security'))


#save all changes after mag-change password
@app.route('/save-security', methods=['POST'])
def save_security():
   user_id = session.get('user_id')
   if not user_id:
       flash("You must be logged in.", "error")
       return redirect(url_for('login'))
  
   # save logic here
   flash('Saved Successfully!', 'success')
   return redirect(url_for('lensHome'))


   # process password change here
   return redirect(url_for('lensHome'))


@app.route('/helpSupport')
def helpSupport():
   return render_template('helpSupport.html')


@app.route('/termsPolicies')
def termsPolicies():
   return render_template('termsPolicies.html')


@app.route('/reportProblem')
def reportProblem():
   return render_template('reportProblem.html')




@app.route('/logout')
def logout():
   session.clear()
   resp = make_response(redirect(url_for('login')))
   resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
   resp.headers['Pragma'] = 'no-cache'
   resp.headers['Expires'] = '0'
   return resp






#FOR GUEST MODE HOMEPAGE
@app.route("/guestHome")
def guestHome():
   year = request.args.get('year', '2025')


   conn = get_db_connection()
   cur = conn.cursor()


   # Municipality with highest crime rate
   cur.execute("""
       SELECT "Municipality", COUNT(*) as total_cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY total_cases DESC
       LIMIT 1
   """, (year,))
   municipality_data = cur.fetchone()   # (Municipality, total_cases) top municipality




   # -----------------------------------------
   # 2️⃣ Most common crime type
   # -----------------------------------------
   cur.execute("""
       SELECT "Crime_Type", COUNT(*) as total_cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Crime_Type"
       ORDER BY total_cases DESC
       LIMIT 1
   """, (year,))
   crime_data = cur.fetchone()           # (Type_of_crime, total_cases) most common crime type




   # -----------------------------------------
   # 3️⃣ Peak month (highest number of crimes)
   # -----------------------------------------
   cur.execute("""
       SELECT "Month", COUNT(*) as total_cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Month"
       ORDER BY total_cases DESC
       LIMIT 1
   """, (year,))
   month_data = cur.fetchone()           # (MonthNumber, total_cases) peak month
  
   # 4️⃣ Total Crime Cases in that year
   cur.execute("""
       SELECT COUNT(*)
       FROM crime_reports
       WHERE "Year" = %s
       """, (year,))
   total_cases = cur.fetchone()[0]




   cur.close()
   conn.close()


   # Unpack the peak month data: month_name is the month (text), month_cases is the number of cases.
   # If month_data is None (no records for the year), default to None and 0.
   month_name, month_cases = month_data if month_data else (None, 0)
  
   # -----------------------------------------
   # Send EVERYTHING to template
   # -----------------------------------------
  
   return render_template(
       "guestHome.html",
       year=year,
       municipality_data=municipality_data,
       crime_data=crime_data,
       month_name=month_name,
       month_cases=month_cases,
       total_cases=total_cases,
       active_page="home"
   )
  
#USER MAP ROUTE
# USER MAP ROUTE
@app.route("/userMap")
def user_map():
   user_id = session.get('user_id')
   if not user_id:
       return redirect('/login')


   # 1️⃣ Municipality from session
   municipality_name = session.get('municipality', 'Default Town')


   # 2️⃣ Year from dropdown (default 2025)
   year = int(request.args.get("year", 2025))


   conn = get_db_connection()
   cur = conn.cursor()


   # 3️⃣ Total cases (COUNT rows)
   cur.execute(
       """
       SELECT COUNT(*)
       FROM crime_reports
       WHERE "Municipality" = %s
         AND "Year" = %s
       """,
       (municipality_name, year)
   )
   total_cases = cur.fetchone()[0] or 0


   # 4️⃣ Top crime (most frequent Crime_Type)
   cur.execute(
       """
       SELECT "Crime_Type", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Municipality" = %s
         AND "Year" = %s
         AND "Crime_Type" != 'Others'
       GROUP BY "Crime_Type"
       ORDER BY cases DESC
       LIMIT 1
       """,
       (municipality_name, year)
   )
   top_crime_data = cur.fetchone()
   if top_crime_data:
       top_crime = top_crime_data[0]
       top_crime_cases = top_crime_data[1]
   else:
       top_crime = "-"
       top_crime_cases = 0


   # 5️⃣ Peak month (month with highest cases)
   cur.execute(
       """
       SELECT "Month", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Municipality" = %s
         AND "Year" = %s
       GROUP BY "Month"
       ORDER BY cases DESC
       LIMIT 1
       """,
       (municipality_name, year)
   )
   peak_month_data = cur.fetchone()
   if peak_month_data:
       peak_month = peak_month_data[0]
       peak_month_cases = peak_month_data[1]
   else:
       peak_month = "-"
       peak_month_cases = 0


   # 6️⃣ Fetch available years for dropdown
   cur.execute(
       """
       SELECT DISTINCT "Year"
       FROM crime_reports
       ORDER BY "Year" DESC
       """
   )
   years = [row[0] for row in cur.fetchall()]


   cur.close()
   conn.close()
  
   if total_cases == 0:
       light_color = "gray"      # no data
   elif total_cases <= 10:
       light_color = "green"     # low crime
   elif total_cases <= 30:
       light_color = "yellow"    # medium crime
   else:
       light_color = "red"


   return render_template(
       "userMap.html",
       municipality=municipality_name,
       total_cases=total_cases,
       top_crime=top_crime,
       top_crime_cases=top_crime_cases,
       peak_month=peak_month,
       peak_month_cases=peak_month_cases,
       year=year,
       years=years,
       active_page = "userMap",
       light_color=light_color
   )
  
  
#search bar sa map
@app.route("/municipality_suggestions")
def municipality_suggestions():
   term = request.args.get("term", "").strip()  # the typed letters


   if not term:
       return jsonify([])  # return empty list if nothing typed


   conn = get_db_connection()
   cur = conn.cursor()
  
   # Get unique municipalities starting with term (case-insensitive)
   cur.execute("""
       SELECT DISTINCT "Municipality"
       FROM crime_reports
       WHERE "Municipality" ILIKE %s
       ORDER BY "Municipality" ASC
       LIMIT 10
   """, (f"{term}%",))
  
   results = [row[0] for row in cur.fetchall()]
  
   cur.close()
   conn.close()
  
   return jsonify(results)


#mini card data sa left search bar
@app.route("/userMap_data")
def user_map_data():
   municipality_name = request.args.get("municipality", session.get("municipality"))
   year = int(request.args.get("year", session.get("year", 2025)))


   # save current state sa session
   session["municipality"] = municipality_name
   session["year"] = year


   conn = get_db_connection()
   cur = conn.cursor()


   # Total cases
   cur.execute("""
       SELECT COUNT(*)
       FROM crime_reports
       WHERE "Municipality" = %s AND "Year" = %s
   """, (municipality_name, year))
   total_cases = cur.fetchone()[0] or 0


   # Top crime
   cur.execute("""
       SELECT "Crime_Type", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Municipality" = %s AND "Year" = %s AND "Crime_Type" != 'Others'
       GROUP BY "Crime_Type"
       ORDER BY cases DESC
       LIMIT 1
   """, (municipality_name, year))
   top_crime_data = cur.fetchone()
   top_crime = top_crime_data[0] if top_crime_data else "-"
   top_crime_cases = top_crime_data[1] if top_crime_data else 0


   # Peak month
   cur.execute("""
       SELECT "Month", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Municipality" = %s AND "Year" = %s
       GROUP BY "Month"
       ORDER BY cases DESC
       LIMIT 1
   """, (municipality_name, year))
   peak_month_data = cur.fetchone()
   peak_month = peak_month_data[0] if peak_month_data else "-"
   peak_month_cases = peak_month_data[1] if peak_month_data else 0


   cur.close()
   conn.close()


   # light color
   if total_cases == 0:
       light_color = "gray"
   elif total_cases <= 10:
       light_color = "green"
   elif total_cases <= 30:
       light_color = "yellow"
   else:
       light_color = "red"


   return jsonify({
       "municipality": municipality_name,
       "year": year,
       "total_cases": total_cases,
       "top_crime": top_crime,
       "top_crime_cases": top_crime_cases,
       "peak_month": peak_month,
       "peak_month_cases": peak_month_cases,
       "light_color": light_color
   })






#GUEST MODE FOR ANALYTICS
@app.route("/guestAnalytics")
def guestAnalytics():
   year = int(request.args.get("year", 2025))
  
   conn = get_db_connection()
   cur = conn.cursor()


   # YEARS FOR DROPDOWN
   cur.execute("""
       SELECT DISTINCT "Year"
       FROM crime_reports
       ORDER BY "Year" DESC
   """)
   years = [row[0] for row in cur.fetchall()]
  
   if not year or int(year) not in years:
       year = years[0]
      
   # 🔹 Total cases per year (whole Pangasinan)
   cur.execute("""
       SELECT COUNT(*)
       FROM crime_reports
       WHERE "Year" = %s
   """, (year,))
   total_cases = cur.fetchone()[0]
  
   # 🔹 Monthly peak (highest crime month of the year)
   cur.execute("""
       SELECT "Month", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Month"
       ORDER BY cases DESC
       LIMIT 1
   """, (year,))


   peak_row = cur.fetchone()
   peak_month, peak_month_cases = peak_row if peak_row else ("-", 0)
  
   # Monthly trend for the whole Pangasinan
   cur.execute("""
       SELECT "Month", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Month"
       ORDER BY "Month" ASC
   """, (year,))
   trend_rows = cur.fetchall()


   # Standard month order
   months_order = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]


   # Make a clean dictionary from query
   month_dict = {}
   for row in trend_rows:
       month_name = row[0].strip().title()  # ensures "january" → "January"
       month_cases = row[1]
       month_dict[month_name] = month_cases


   # Fill missing months with 0 and preserve order
   months = []
   cases = []
   for m in months_order:
       months.append(m)
       cases.append(month_dict.get(m, 0))




      
   # 🔹 Top 3 municipalities (for mini card)
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY cases DESC
       LIMIT 3
   """, (year,))
   top3_munis = cur.fetchall()  # [(Mun1, cases), (Mun2, cases), (Mun3, cases)]
   top3_labels = [row[0] for row in top3_munis]
   top3_values = [row[1] for row in top3_munis]
  
       # 🔹 All municipalities (View All)
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY cases DESC
   """, (year,))
   all_munis = cur.fetchall()
   all_labels = [row[0] for row in all_munis]
   all_values = [row[1] for row in all_munis]




   # 🔹 Top Municipality overall (total cases, filtered by year)
   cur.execute("""
       SELECT "Municipality", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       GROUP BY "Municipality"
       ORDER BY cases DESC
       LIMIT 1;
   """, (year,))
   top_muni_row = cur.fetchone()
   top_municipality, top_municipality_cases = top_muni_row if top_muni_row else ("-", 0)


   # 🔹 Most Common Crime Type overall (filtered by year)
   cur.execute("""
       SELECT "Crime_Type", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Year" = %s
       AND "Crime_Type" != 'Others'
       GROUP BY "Crime_Type"
       ORDER BY cases DESC
       LIMIT 1;
   """, (year,))
   common_crime_row = cur.fetchone()
   if common_crime_row:
       common_crime, common_crime_cases = common_crime_row
   else:
       common_crime, common_crime_cases = "-", 0


   # 🔹 Table: Top Municipality per Crime Type (exclude 'Others')
   cur.execute("""
       SELECT crime, municipality, cases
       FROM (
           SELECT
               "Crime_Type" AS crime,
               "Municipality" AS municipality,
               COUNT(*) AS cases,
               ROW_NUMBER() OVER(
                   PARTITION BY "Crime_Type"
                   ORDER BY COUNT(*) DESC
               ) AS rn
           FROM crime_reports
           WHERE "Year" = %s
           AND "Crime_Type" != 'Others'
           GROUP BY "Crime_Type", "Municipality"
       ) t
       WHERE rn = 1
       ORDER BY
           CASE crime
               WHEN 'Robbery' THEN 1
               WHEN 'Vandalism' THEN 2
               WHEN 'Drugs' THEN 3
               WHEN 'Rape' THEN 4
               WHEN 'Abuse' THEN 5
               WHEN 'Theft' THEN 6
               WHEN 'Homicide' THEN 7
               ELSE 8
           END;
   """, (year,))




   table_data = [
       {"crime": row[0], "municipality": row[1], "cases": row[2]}
       for row in cur.fetchall()
   ]


   cur.close()
   conn.close()


   return render_template(
       "guestAnalytics.html",
       total_cases=total_cases,
       years=years,
       selected_year=int(year),
       top_municipality=top_municipality,
       top_municipality_cases=top_municipality_cases,
       common_crime=common_crime,
       table_data=table_data,
       peak_month=peak_month,
       peak_month_cases=peak_month_cases,
       common_crime_cases=common_crime_cases,
       trend_months=months,
       trend_cases=cases,
       municipality_names=top3_labels,   # ✅ top 3 municipalities for initial chart
       municipality_cases=top3_values,   # ✅ initial values
       all_municipality_names=all_labels,  # ✅ all municipalities for "View All"
       all_municipality_cases=all_values,
       active_page="analytics"
   )
  
@app.route("/guestMap")
def guestMap():
   # user_id = session.get('user_id')
   # if not user_id:
   #     return redirect('/login')


   # 1️⃣ Municipality from session
   municipality_name = session.get('municipality', 'Default Town')


   # 2️⃣ Year from dropdown (default 2025)
   year = int(request.args.get("year", 2025))


   conn = get_db_connection()
   cur = conn.cursor()


   # 3️⃣ Total cases (COUNT rows)
   cur.execute(
       """
       SELECT COUNT(*)
       FROM crime_reports
       WHERE "Municipality" = %s
         AND "Year" = %s
       """,
       (municipality_name, year)
   )
   total_cases = cur.fetchone()[0] or 0


   # 4️⃣ Top crime (most frequent Crime_Type)
   cur.execute(
       """
       SELECT "Crime_Type", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Municipality" = %s
         AND "Year" = %s
         AND "Crime_Type" != 'Others'
       GROUP BY "Crime_Type"
       ORDER BY cases DESC
       LIMIT 1
       """,
       (municipality_name, year)
   )
   top_crime_data = cur.fetchone()
   if top_crime_data:
       top_crime = top_crime_data[0]
       top_crime_cases = top_crime_data[1]
   else:
       top_crime = "-"
       top_crime_cases = 0


   # 5️⃣ Peak month (month with highest cases)
   cur.execute(
       """
       SELECT "Month", COUNT(*) AS cases
       FROM crime_reports
       WHERE "Municipality" = %s
         AND "Year" = %s
       GROUP BY "Month"
       ORDER BY cases DESC
       LIMIT 1
       """,
       (municipality_name, year)
   )
   peak_month_data = cur.fetchone()
   if peak_month_data:
       peak_month = peak_month_data[0]
       peak_month_cases = peak_month_data[1]
   else:
       peak_month = "-"
       peak_month_cases = 0


   # 6️⃣ Fetch available years for dropdown
   cur.execute(
       """
       SELECT DISTINCT "Year"
       FROM crime_reports
       ORDER BY "Year" DESC
       """
   )
   years = [row[0] for row in cur.fetchall()]


   cur.close()
   conn.close()
  
   if total_cases == 0:
       light_color = "gray"      # no data
   elif total_cases <= 10:
       light_color = "green"     # low crime
   elif total_cases <= 30:
       light_color = "yellow"    # medium crime
   else:
       light_color = "red"


   # 7️⃣ Render template
   return render_template(
       "guestMap.html",
       municipality=municipality_name,
       total_cases=total_cases,
       top_crime=top_crime,
       top_crime_cases=top_crime_cases,
       peak_month=peak_month,
       peak_month_cases=peak_month_cases,
       year=year,
       years=years,
       active_page = "guestMap",
       light_color=light_color
   )


if __name__ == "__main__":
   app.run(debug=True)



