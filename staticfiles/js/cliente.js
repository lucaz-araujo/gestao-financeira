$(function () {

  /* Functions */

  var loadForm = function () {
    $.ajax({
      url: $(this).data("form"),
      type: 'get',
      dataType: 'json',
      success: function (data) {
        $("#editModal .modal-content").html(data.html_form);
      }
    });
  };

  var saveForm = function () {
    var form = $(this);
    $.ajax({
      url: form.attr("action"),
      data: form.serialize(),
      type: form.attr("method"),
      dataType: 'json',
      success: function (data) {
        if (data.form_is_valid) {
          // $("#dataTables-example tbody").html(data.html_clientes_list);
          $("#editModal").modal("hide");
          $("#btn_pesquisa").trigger('click');
        }
        else {
          $("#editModal .modal-content").html(data.html_form);
        }
      }
    });
    return false;
  };


  /* Binding */

  // Create book
  $(".js-create-cliente").click(loadForm);
  $("#editModal").on("submit", ".js-cliente-create-form", saveForm);

  // Update book
  $("#dataTables-example").on("click", ".js-update-cliente", loadForm);
  $("#editModal").on("submit", ".js-cliente-update-form", saveForm);


});