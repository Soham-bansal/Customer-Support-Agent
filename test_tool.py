from tools import issue_refund, flag_for_review, send_email, get_order, check_refund_eligibility

print(issue_refund("O-1010", 300, "test refund"))
print(get_order("O-1010")["amount_refunded"])
print(check_refund_eligibility("O-1010")["decision"])
print(flag_for_review("O-1009", "test flag"))
send_email("ravi.nair@example.com", "Test", "Hello")



