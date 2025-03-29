from flask import Flask,render_template

app=Flask("Hello")

@app.route("/")
def welcome():
    return render_template('test.html')

@app.route("/index",)
def index():
    return "Welcome to this index page of host"

if __name__ == "__main__":
    app.run(debug=True)