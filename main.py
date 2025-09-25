import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


def main():
    st.title("My Supply Chain Dashboard")
    st.write("Hello World!")

    # Your charts/graphs go here
    data = pd.DataFrame({'x': [1,2,3], 'y':
    [1,4,9]})
    st.line_chart(data)


if __name__ == "__main__":
    main()
